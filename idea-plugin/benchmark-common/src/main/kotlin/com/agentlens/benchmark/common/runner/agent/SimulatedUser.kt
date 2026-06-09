package com.agentlens.benchmark.common.runner.agent

import com.agentlens.benchmark.common.schema.MessageKind
import com.agentlens.benchmark.common.runner.getBenchJson
import com.agentlens.benchmark.common.schema.AgentBenchMessage
import com.agentlens.benchmark.common.schema.AgentBenchResponse
import com.agentlens.benchmark.common.schema.LlmUsage
import com.agentlens.benchmark.common.utils.ChangeType
import com.agentlens.benchmark.common.utils.CodeDiff
import com.agentlens.benchmark.common.utils.getChangedFiles
import com.agentlens.benchmark.common.utils.trimAndPrependInnerBlock
import com.agentlens.benchmark.common.utils.visibleName
import com.agentlens.benchmark.common.utils.staticAnalysis.StaticAnalysisUtils
import com.agentlens.benchmark.common.utils.staticAnalysis.StaticAnalysisUtils.SeverityLevel
import com.agentlens.benchmark.common.utils.findVirtualFileInTheProject
import com.intellij.diff.comparison.ComparisonManager
import com.intellij.diff.comparison.ComparisonPolicy
import com.intellij.openapi.application.EDT
import com.intellij.openapi.application.readAction
import com.intellij.openapi.progress.EmptyProgressIndicator
import com.intellij.openapi.project.Project
import com.intellij.openapi.vcs.changes.ChangeListManager
import com.intellij.openapi.vcs.changes.InvokeAfterUpdateMode
import com.intellij.openapi.vcs.changes.VcsDirtyScopeManager
import com.intellij.openapi.vfs.VirtualFileManager
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlinx.serialization.ExperimentalSerializationApi
import kotlinx.serialization.json.encodeToStream
import org.springframework.ai.chat.model.ChatResponse as SpringChatResponse
import org.springframework.ai.chat.prompt.Prompt as SpringPrompt
import org.springframework.ai.chat.messages.SystemMessage
import org.springframework.ai.chat.messages.UserMessage
import org.springframework.ai.chat.messages.AssistantMessage
import org.springframework.ai.chat.messages.ToolResponseMessage
import org.springframework.ai.chat.messages.Message as SpringMessage
import org.springframework.ai.openai.OpenAiChatModel
import org.springframework.ai.openai.OpenAiChatOptions
import org.springframework.ai.openai.api.OpenAiApi
import java.nio.file.Files
import java.nio.file.Path
import kotlin.coroutines.resume
import kotlin.io.path.exists
import kotlin.io.path.readLines
import kotlin.io.path.writeText
import kotlin.time.Duration
import kotlin.time.Duration.Companion.minutes
import kotlin.time.measureTimedValue
import com.agentlens.benchmark.common.schema.Message
import com.agentlens.benchmark.common.schema.ToolCall
import com.jetbrains.rd.util.UUID


data class FileIdeErrors(
    val path: String,
    val amount: Int,
    val descriptions: List<IdeErrorDescription>,
)

data class IdeErrorDescription(
    val lineContent: String,
    val errorMessage: String,
)

data class SimulatedUserResponse(
    val response: String = "",
    val toolCalls: List<ToolCall> = emptyList(),
    val usage: LlmUsage = LlmUsage(),
)

class SimulatedUser private constructor(
    userKind: String,
    taskDescription: String,
    agentName: String,
    private val project: Project,
    private val chatModel: OpenAiChatModel,
    private val modelName: String,
    private val flushChangesBeforeGettingDiff: Boolean
) {
    private val useCase = SimulatedUserUseCase(project)
    private val systemPrompt: Message = Message.system(
        useCase.makeSystemPrompt(userKind, taskDescription, agentName)
    )
    private var currentTurn = 0

    suspend fun getAgentTrace(): AgentTrace {
        val currCodeDiffs = getCodeDiffs()
        val filesToAnalyze = currCodeDiffs.mapNotNull { project.findVirtualFileInTheProject(it.path) }
        val currProjectErrors: List<FileIdeErrors> = if (filesToAnalyze.isNotEmpty()) {
            StaticAnalysisUtils.getAnalysisResults(project, filesToAnalyze, SeverityLevel.ERROR, 10.minutes)
                ?.groupBy { it.file }
                ?.filter { (file, problems) -> Path.of(file).exists() && problems.isNotEmpty() }
                ?.map { (file, problems) ->
                    val fileLines = Path.of(file).readLines()
                    FileIdeErrors(
                        file,
                        problems.size,
                        problems.map { problem ->
                            IdeErrorDescription(
                                fileLines.getOrElse(problem.line - 1) { "Failed to extract line content" },
                                problem.description,
                            )
                        }
                    )
                } ?: emptyList<FileIdeErrors>().also { logger.error { "Failed to get project errors" } }
        } else emptyList()

        return AgentTrace(currCodeDiffs, currProjectErrors)
    }

    @OptIn(ExperimentalSerializationApi::class)
    suspend fun generateNext(realHistory: List<Message>, messageDir: Path, repeatCount: Int = 5): SimulatedUserResponse? {
        if (realHistory.lastOrNull()?.type == MessageKind.USER) {
            logger.error { "No agent actions since last user message" }
            return null
        }

        val simulatedHistory = makeHistorySimulation(realHistory)

        val agentTracePrompt: String = composeAgentTracePrompt(getAgentTrace())

        val messages = if (simulatedHistory.size <= 1) {
            simulatedHistory
        } else {
            appendAgentTrace(simulatedHistory, agentTracePrompt)
        }

        var response: SimulatedUserResponse
        var time: Duration
        var count = 0
        val firstMessage = simulatedHistory.find { it.type == MessageKind.ASSISTANT } == null
        do {
            var dialogTerminated = false
            val (newResponse, newTime) = measureTimedValue {
                val response = getSimulatedResponse(messages)
                if (response.toolCalls.firstOrNull()?.name == TerminationTool.NAME) {
                    dialogTerminated = true
                    val arguments = response.toolCalls.first().arguments
                    response.copy(
                        response = if (response.response.isNotBlank()) {
                            "Response:\n${response.response}\nTermination tool arguments:\n$arguments"
                        } else {
                            "Termination tool arguments:\n$arguments"
                        }
                    )
                } else response
            }
            response = newResponse
            time = newTime
            count++
        } while (firstMessage && dialogTerminated && count < repeatCount) // prevent early termination on the first user message

        runCatching {
            val request = listOf(AgentBenchMessage(systemPrompt.type.visibleName, systemPrompt.text)) +
                    messages.map { message ->
                        AgentBenchMessage(
                            role = when (message.type) {
                                MessageKind.USER -> MessageKind.ASSISTANT.visibleName
                                MessageKind.ASSISTANT -> MessageKind.USER.visibleName
                                else -> message.type.visibleName
                            },
                            content = message.text,
                        )
                    }

            val agentBenchResponse = AgentBenchResponse(
                role = "simulator",
                request = request,
                response = AgentBenchMessage(MessageKind.USER.visibleName, response.response),
                responsePrice = response.usage.price,
                responseTime = time.inWholeSeconds,
            )

            val fileNameSuffix = currentTurn.toString().padStart(3, '0')
            val jsonFilePath = messageDir.resolve("simulated_user_${fileNameSuffix}.json")
            Files.newOutputStream(jsonFilePath).use { output ->
                getBenchJson().encodeToStream(agentBenchResponse, output)
            }

            val readableFilePath = messageDir.resolve("simulated_user_${fileNameSuffix}.txt")
            val requestText = "PROMPTS:\n${request.joinToString("") { "\n${it.role}\n```\n${it.content}\n```\n" }}\n\n"
            val responseText = "RESPONSE:\n```\n${response.response}\n```"
            readableFilePath.writeText(requestText + responseText)
        }.onFailure {
            logger.error { "Failed to log simulated user response: ${it.message}" }
        }

        currentTurn++

        return response
    }

    private suspend fun getSimulatedResponse(messages: List<Message>): SimulatedUserResponse {
        val springMessages: List<SpringMessage> = buildList {
            add(SystemMessage(systemPrompt.text))
            for (msg in messages) {
                add(msg.toSpringAi())
            }
        }

        val prompt = SpringPrompt(springMessages)
        logger.debug { "Sending user message to ${modelName}: $prompt" }

        val springResponses: List<SpringChatResponse> = withContext(Dispatchers.IO) {
            chatModel.stream(prompt).collectList().block().orEmpty()
        }

        return springResponses.toSimulatedUserResponse()
    }

    private fun List<SpringChatResponse>.toSimulatedUserResponse(): SimulatedUserResponse {
        val responseText = StringBuilder()
        val toolCalls = mutableListOf<ToolCall>()
        var usage: org.springframework.ai.chat.metadata.Usage? = null

        for (chatResponse in this) {
            val aiMessage = chatResponse.result.output
            aiMessage.text?.let(responseText::append)
            aiMessage.toolCalls.forEach { req ->
                toolCalls += ToolCall(
                    id = req.id() ?: "",
                    name = req.name(),
                    arguments = req.arguments(),
                )
            }
            chatResponse.metadata.usage?.takeIf { (it.totalTokens ?: 0) > 0 }?.let { usage = it }
        }

        val promptTokens = usage?.promptTokens?.toLong() ?: 0L
        val completionTokens = usage?.completionTokens?.toLong() ?: 0L

        // Extract cache hit tokens from native OpenAI usage object
        val cachedTokens = extractCachedTokens(usage)

        val price = PriceCalculator.calculatePrice(
            modelName = modelName,
            promptTokens = promptTokens,
            completionTokens = completionTokens,
            cachedTokens = cachedTokens,
        )

        return SimulatedUserResponse(
            response = responseText.toString(),
            toolCalls = toolCalls,
            usage = LlmUsage(
                price = price,
                promptTokens = promptTokens,
                generationTokens = completionTokens,
                promptCacheHitTokens = cachedTokens.takeIf { it > 0 },
            ),
        )
    }

    /**
     * Attempts to extract the number of cached prompt tokens from the native OpenAI usage payload.
     * Falls back to 0 if not available.
     */
    private fun extractCachedTokens(usage: org.springframework.ai.chat.metadata.Usage?): Long {
        if (usage == null) return 0L
        val native = usage.nativeUsage ?: return 0L
        // Spring AI OpenAI adapter returns OpenAiApi.Usage which has promptTokensDetails
        return try {
            val nativeUsage = native as? OpenAiApi.Usage ?: return 0L
            nativeUsage.promptTokensDetails()?.cachedTokens()?.toLong() ?: 0L
        } catch (_: Exception) {
            0L
        }
    }

    private fun makeHistorySimulation(history: List<Message>): List<Message> {
        // trim tool content and swap message types
        val compressedMessages = history.mapIndexedNotNull { idx, message ->
            when (message.type) {
                MessageKind.SYSTEM -> {
                    null
                }

                MessageKind.USER -> {
                    message.copy(type = MessageKind.ASSISTANT)
                }

                MessageKind.ASSISTANT -> {
                    if (idx <= 1) {
                        return@mapIndexedNotNull message.copy(type = MessageKind.USER)
                    }

                    val toolRepresentation = message.toolCalls.joinToString(separator = "\n\n") { toolCall ->
                        """
                    **Tool name**: ${toolCall.name}
                    **Tool args**:
                    ${trimIfLongWithMessage(toolCall.arguments, trimLimit=5000).trimAndPrependInnerBlock()}
                    """.trimIndent().trimMargin()
                    }

                    val simulatorMessageText = buildString {
                        if (message.text.isNotBlank()) {
                            append(
                                """
                                <agent_response>
                                ${message.text.trimAndPrependInnerBlock()}
                                </agent_response>
                                """.trimIndent().trimMargin()
                            )
                        }

                        if (toolRepresentation.isNotBlank()) {
                            append(
                                """
                                <tool_calls>:
                                ${toolRepresentation.trimAndPrependInnerBlock()}
                                </tool_calls>
                                """.trimIndent().trimMargin()
                            )
                        }
                    }.ifBlank {
                        "Empty response"
                    }

                    message.copy(
                        type = MessageKind.USER,
                        text = simulatorMessageText,
                        toolCalls = emptyList(),
                        reasoning = null,
                    )
                }

                MessageKind.TOOL -> {
                    val toolResponseRepresentation = message.toolResponses
                        .joinToString(separator = "\n\n") { toolResponse ->
                            """
                            **Tool name**: ${toolResponse.name}
                            **Tool response**: 
                            ${trimIfLongWithMessage(toolResponse.responseData, trimLimit=10000).trimAndPrependInnerBlock()}
                            """.trimIndent().trimMargin()
                        }
                    message.copy(
                        type = MessageKind.USER,
                        text =
                            """
                            <tool_responses>:
                            ${toolResponseRepresentation.trimAndPrependInnerBlock()}
                            </tool_responses>
                            """.trimIndent().trimMargin()
                    )
                }
            }
        }

        // accumulate consequent agent and tool messages into one "USER" message
        val simulatorFriendlyHistory: List<Message> =
            compressedMessages.fold(mutableListOf()) { acc, msg ->
                if (msg.type == MessageKind.USER && acc.lastOrNull()?.type == MessageKind.USER) {
                    val last = acc.removeLast()
                    acc.add(last.copy(text = last.text + "\n\n" + msg.text))
                } else {
                    acc.add(msg)
                }
                acc
            }

        return simulatorFriendlyHistory
    }

    private fun appendAgentTrace(history: List<Message>, agentTrace: String): List<Message> =
        with(history.last()) { history.dropLast(1) + copy(text = "$text\n\n$agentTrace") }

    private suspend fun getCodeDiffs(): List<CodeDiff> {
        if (flushChangesBeforeGettingDiff) {
            flushExternalFileChanges()
        }
        val changedFiles = getChangedFiles(project)
        return changedFiles.map { file ->
            when (file.changeType) {
                ChangeType.MODIFIED, ChangeType.MOVED -> {
                    val beforeContent = file.beforeContent ?: ""
                    val afterContent = file.afterContent ?: ""
                    val afterPath = file.afterPath ?: file.path
                    val beforePath = file.beforePath ?: afterPath
                    CodeDiff(file.path, getModifiedDiff(beforeContent, afterContent, beforePath, afterPath))
                }

                ChangeType.NEW -> {
                    val after = file.afterContent ?: ""
                    CodeDiff(file.path, "+++ ${file.path}\n$after")
                }

                ChangeType.DELETED -> {
                    val before = file.beforeContent ?: ""
                    CodeDiff(file.path, "--- ${file.path}\n$before")
                }
            }
        }
    }

    private suspend fun flushExternalFileChanges() {
        logger.info { "[SimulatedUser] Flushing external file changes" }
        withContext(Dispatchers.EDT) {
            VirtualFileManager.getInstance().refreshWithoutFileWatcher(false)
            readAction {
                VcsDirtyScopeManager.getInstance(project).markEverythingDirty()
            }
        }
        suspendCancellableCoroutine { continuation ->
            ChangeListManager.getInstance(project).invokeAfterUpdate(
                { continuation.resume(Unit) },
                InvokeAfterUpdateMode.SILENT,
                /* title */ null,
                /* runnable */ null
            )
        }
        logger.info { "[SimulatedUser] ChangeListManager update complete" }
    }

    private fun getModifiedDiff(
        beforeContent: String,
        afterContent: String,
        beforePath: String,
        afterPath: String,
    ): String {
        val comparisonManager = ComparisonManager.getInstance()
        val fragments = comparisonManager.compareLines(
            beforeContent,
            afterContent,
            ComparisonPolicy.DEFAULT,
            EmptyProgressIndicator()
        )

        val beforeLines = beforeContent.lines()
        val afterLines = afterContent.lines()

        return buildString {
            if (beforePath != afterPath) {
                appendLine("Moved: $beforePath -> $afterPath")
            }

            if (fragments.isNotEmpty()) {
                appendLine("--- $beforePath")
                appendLine("+++ $afterPath")
            }

            for (fragment in fragments) {
                val beforeStart = fragment.startLine1
                val beforeEnd = fragment.endLine1
                val afterStart = fragment.startLine2
                val afterEnd = fragment.endLine2

                appendLine("@@ -${beforeStart + 1},${beforeEnd - beforeStart} +${afterStart + 1},${afterEnd - afterStart} @@")

                for (i in beforeStart until beforeEnd) {
                    appendLine("-${beforeLines[i]}")
                }

                for (i in afterStart until afterEnd) {
                    appendLine("+${afterLines[i]}")
                }
            }
        }
    }

    companion object {
        private val PROMPT_CACHE_KEY = UUID.randomUUID().toString() // unique key per plugin

        fun create(
            userKind: String,
            taskDescription: String,
            project: Project,
            /* Needed for external engines only */
            flushChangesBeforeGettingDiff: Boolean,
            agentName: String,
        ): SimulatedUser {
            val simulatorModelName = AgentEnvService.getEnvValue(EnvVariable.SIMULATOR_MODEL_NAME)
                ?: error("${EnvVariable.SIMULATOR_MODEL_NAME} environment variable is not set")
            val simulatorBaseUrl = AgentEnvService.getEnvValue(EnvVariable.SIMULATOR_BASE_URL)
                ?: error("${EnvVariable.SIMULATOR_BASE_URL} environment variable is not set")
            val apiKey = AgentEnvService.getEnvValue(EnvVariable.SIMULATOR_API_KEY)
                ?: error("${EnvVariable.SIMULATOR_API_KEY} environment variable is not set")

            val openAiApi = OpenAiApi.builder()
                .baseUrl(simulatorBaseUrl)
                .apiKey(apiKey.trim())
                .build()

            val terminationFunction = OpenAiApi.FunctionTool.Function(
                TerminationTool.description,
                TerminationTool.NAME,
                TerminationTool.termination_tool_schema,
            )
            val terminationTool = OpenAiApi.FunctionTool(terminationFunction)

            val chatOptionsWithTools = OpenAiChatOptions.builder()
                .model(simulatorModelName)
                .tools(listOf(terminationTool))
                .internalToolExecutionEnabled(false)
                .streamUsage(true) // include token usage in the final streamed chunk
                .build()

            val chatModel = OpenAiChatModel.builder()
                .openAiApi(openAiApi)
                .defaultOptions(chatOptionsWithTools)
                .build()

            return SimulatedUser(
                userKind = userKind,
                taskDescription = taskDescription,
                agentName = agentName,
                project = project,
                chatModel = chatModel,
                modelName = simulatorModelName,
                flushChangesBeforeGettingDiff = flushChangesBeforeGettingDiff,
            )
        }
    }
}

data class AgentTrace(
    val currCodeDiffs: List<CodeDiff>,
    val currProjectErrors: List<FileIdeErrors>
)

private fun Message.toSpringAi(): SpringMessage {
    return when (type) {
        MessageKind.SYSTEM -> SystemMessage(text)
        MessageKind.USER -> UserMessage(text)
        MessageKind.ASSISTANT -> {
            val toolRequests = toolCalls.map { tc ->
                AssistantMessage.ToolCall(tc.id, "function", tc.name, tc.arguments)
            }
            AssistantMessage.builder()
                .content(text)
                .toolCalls(toolRequests)
                .build()
        }
        MessageKind.TOOL -> {
            val toolResps = toolResponses.map { tr -> ToolResponseMessage.ToolResponse(tr.id, tr.name, tr.responseData) }
            ToolResponseMessage.builder()
                .responses(toolResps)
                .build()

        }
    }
}
