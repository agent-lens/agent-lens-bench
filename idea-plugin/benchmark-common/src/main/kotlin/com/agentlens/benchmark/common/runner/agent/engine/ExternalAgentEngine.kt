package com.agentlens.benchmark.common.runner.agent.engine

import com.agentlens.benchmark.common.dialogs.ModelSettings
import com.agentlens.benchmark.common.runner.agent.AgentTurnUsageInfo
import com.agentlens.benchmark.common.schema.AgentScenarioSettings
import com.agentlens.benchmark.common.schema.BenchHttpMcpServerConfiguration
import com.agentlens.benchmark.common.schema.Message
import com.agentlens.benchmark.common.schema.MessageKind
import com.agentlens.benchmark.common.schema.MessageToolCalls
import com.agentlens.benchmark.common.schema.ToolCallHistoryEntry
import com.agentlens.benchmark.common.schema.UserRequest
import com.agentlens.benchmark.common.utils.JsonUtils
import com.intellij.openapi.project.Project
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.delay
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.Transient
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.util.*
import kotlin.system.measureTimeMillis

@Serializable
@SerialName("RestAgentEngine")
@Suppress("PROVIDED_RUNTIME_TOO_LOW")
class ExternalAgentEngine(
    val serverUrl: String
) : AgentEngine {

    // TODO: get agent name from server
    override fun getAgentName(): String = "Claude Code"

    @Transient
    private val client = HttpAgentEngineClient(
        serverUrl
    )

    @Transient
    private lateinit var sessionId: UUID

    @Transient
    private lateinit var projectPath: String

    @Transient
    private val usageInfoList = mutableListOf<AgentTurnUsageInfo>()

    @Transient
    private var lastProcessedMessageId: UUID? = null

    @Transient
    private lateinit var chatHistory: MutableList<Message>

    @Transient
    private var configuredModelName: String = ""

    @Transient
    private var configuredMcpServers: Map<String, McpServerConfig> = emptyMap()

    override suspend fun initModelProviderBeforeBenchmarkRun(settings: ModelSettings): String {
        configuredModelName = settings.modelName
        return configuredModelName
    }

    private fun initMcpServersBeforeScenarioRun(mcpServers: List<BenchHttpMcpServerConfiguration>) {
        configuredMcpServers = mcpServers.associate {
            it.name to McpServerConfig(
                it.getTransportType().lowercase(),
                it.url,
                it.headers
            )
        }
    }

    override suspend fun initBeforeScenarioRun(
        project: Project,
        chatHistory: MutableList<Message>,
        agentSettings: AgentScenarioSettings,
    ) {
        initMcpServersBeforeScenarioRun(agentSettings.mcpServers)

        usageInfoList.clear()
        lastProcessedMessageId = null
        this.chatHistory = chatHistory
        projectPath = project.basePath ?: error("Project path is null")

        val agentSettings = ClientAgentSettings(
            modelName = configuredModelName,
            mcpServers = configuredMcpServers
        )

        lastProcessedMessageId = chatHistory.lastOrNull()?.id
        val sessionInfo = client.newSession(agentSettings, projectPath, chatHistory)
        sessionId = sessionInfo.id

        waitForSessionReady()
    }

    override suspend fun sendRequestWithTimeout(request: UserRequest, timeoutSeconds: Long) {
        val sessionInfo = client.getSessionInfo(sessionId)
        if (sessionInfo.state != SessionState.READY) {
            error("Session is not ready. Current state: ${sessionInfo.state}")
        }

        try {
            var finalSessionInfo: SessionInfo? = null
            val timeElapsed = measureTimeMillis {
                withTimeout(timeoutSeconds * 1000) {
                    client.submitUserMessage(request.prompt, timeoutSeconds * 1000)
                    finalSessionInfo = waitForAgentResponse()
                }
            } / 1000

            collectUsageInfo(finalSessionInfo, timeElapsed)
        } catch (e: TimeoutCancellationException) {
            collectUsageInfo(sessionInfo = null, timeElapsedSeconds = timeoutSeconds)
            throw e
        }
    }

    override fun forceTerminateScenarioRun() {
    }

    override fun getUsages(): List<AgentTurnUsageInfo> {
        return usageInfoList
    }

    override suspend fun getChatDump(): String {
        return client.getRawChatDump(sessionId)
    }

    override suspend fun getToolCallsDump(): List<MessageToolCalls> {
        val rawChatDump = client.getRawChatDump(sessionId)
        val root = JsonUtils.json.parseToJsonElement(rawChatDump).jsonObject
        val rawMessages = root[RAW_MESSAGES_FIELD]?.jsonArray ?: return emptyList()

        val toolResponseByToolUseId = parseToolResponses(rawMessages)

        val result = mutableListOf<MessageToolCalls>()
        var assistantMessageIndex = -1

        for (rawMsg in rawMessages) {
            val msgObj = rawMsg.jsonObject
            val type = msgObj[RAW_TYPE_FIELD]?.jsonPrimitive?.contentOrNull ?: continue
            if (!type.endsWith(RAW_AGENT_TURN_SUFFIX)) continue

            assistantMessageIndex++

            val rawToolCalls = msgObj[RAW_TOOL_CALLS_FIELD] as? JsonArray ?: continue
            if (rawToolCalls.isEmpty()) continue

            val calls = rawToolCalls.mapNotNull { rawToolCallWrapper ->
                val toolCallObj = rawToolCallWrapper.jsonObject[RAW_TOOL_CALL_FIELD]?.jsonObject ?: return@mapNotNull null
                val toolUseId = toolCallObj[RAW_ID_FIELD]?.jsonPrimitive?.contentOrNull ?: return@mapNotNull null
                val name = toolCallObj[RAW_NAME_FIELD]?.jsonPrimitive?.contentOrNull ?: UNKNOWN_TOOL_NAME
                val input = toolCallObj[RAW_INPUT_FIELD] ?: JsonObject(emptyMap())

                // Keep backward-compatible shape expected by review/markdown tooling.
                val arguments = buildJsonObject {
                    put(RAW_TOOL_USE_ID_FIELD, JsonPrimitive(toolUseId))
                    put(RAW_INPUT_FIELD, input)
                }.toString()

                val toolResponse = toolResponseByToolUseId[toolUseId]

                ToolCallHistoryEntry(
                    name = name,
                    arguments = arguments,
                    success = toolResponse?.success ?: true,
                    responseContent = toolResponse?.content ?: "",
                    systemReminder = ""
                )
            }

            if (calls.isNotEmpty()) {
                result += MessageToolCalls(
                    assistantMessageIndex = assistantMessageIndex,
                    calls = calls
                )
            }
        }

        return result
    }

    private data class RawToolResponse(
        val success: Boolean,
        val content: String,
    )

    private fun parseToolResponses(rawMessages: JsonArray): Map<String, RawToolResponse> {
        val responses = mutableMapOf<String, RawToolResponse>()

        for (rawMsg in rawMessages) {
            val msgObj = rawMsg.jsonObject
            val type = msgObj[RAW_TYPE_FIELD]?.jsonPrimitive?.contentOrNull ?: continue
            if (!type.endsWith(RAW_TOOL_MESSAGE_SUFFIX)) continue

            val toolCallObj = msgObj[RAW_TOOL_CALL_FIELD]?.jsonObject ?: continue
            val toolUseId = toolCallObj[RAW_ID_FIELD]?.jsonPrimitive?.contentOrNull ?: continue

            val toolResponseObj = msgObj[RAW_TOOL_RESPONSE_FIELD]?.jsonObject ?: continue
            val success = toolResponseObj[RAW_SUCCESS_FIELD]?.jsonPrimitive?.booleanOrNull ?: true
            val content = when (val rawContent = toolResponseObj[RAW_CONTENT_FIELD]) {
                null, JsonNull -> ""
                is JsonPrimitive -> rawContent.contentOrNull ?: ""
                else -> rawContent.toString()
            }

            responses[toolUseId] = RawToolResponse(success = success, content = content)
        }

        return responses
    }

    companion object {
        private const val UNKNOWN_TOOL_NAME = "UNKNOWN"

        private const val RAW_MESSAGES_FIELD = "messages"
        private const val RAW_TYPE_FIELD = "type"

        private const val RAW_AGENT_TURN_SUFFIX = "AgentTurn"
        private const val RAW_TOOL_MESSAGE_SUFFIX = "ToolMessage"

        private const val RAW_TOOL_CALLS_FIELD = "toolCalls"

        // Note: in AgentTurn this is wrapper object containing `toolCall: {id,name,input}`.
        private const val RAW_TOOL_CALL_FIELD = "toolCall"

        // In ToolMessage: `toolCall: {id, name}`.
        private const val RAW_TOOL_RESPONSE_FIELD = "toolResponse"

        private const val RAW_ID_FIELD = "id"
        private const val RAW_NAME_FIELD = "name"
        private const val RAW_INPUT_FIELD = "input"

        private const val RAW_TOOL_USE_ID_FIELD = "tool_use_id"

        private const val RAW_SUCCESS_FIELD = "success"
        private const val RAW_CONTENT_FIELD = "content"
    }

    private suspend fun waitForSessionReady() {
        val maxWaitTimeMillis = 60_000L
        val pollIntervalMillis = 500L
        val startTime = System.currentTimeMillis()

        while (System.currentTimeMillis() - startTime < maxWaitTimeMillis) {
            val sessionInfo = client.getSessionInfo(sessionId)
            when (sessionInfo.state) {
                SessionState.READY -> return
                SessionState.UNINITIALIZED, SessionState.BUSY -> delay(pollIntervalMillis)
            }
        }

        error("Session did not become ready within timeout")
    }

    private suspend fun waitForAgentResponse(): SessionInfo {
        val pollIntervalMillis = 500L

        while (true) {
            val sessionInfo = client.getSessionInfo(sessionId)

            if (sessionInfo.timeout) {
                error("Agent request timed out")
            }

            if (sessionInfo.error != null) {
                error("Agent session error (errorTimestamp=${sessionInfo.errorTimestamp}): ${sessionInfo.error}")
            }

            val newMessages = client.getMessages(fromExcl = lastProcessedMessageId, toIncl = null)
                .filter { it.type != MessageKind.USER }
            newMessages.forEach { msg ->
                chatHistory.add(msg)
            }
            if (newMessages.isNotEmpty()) {
                lastProcessedMessageId = newMessages.last().id
            }

            when (sessionInfo.state) {
                SessionState.READY -> {
                    if (sessionInfo.lastMessageId != null && sessionInfo.lastMessageId == lastProcessedMessageId) {
                        return sessionInfo
                    }
                }

                SessionState.BUSY -> delay(pollIntervalMillis)
                SessionState.UNINITIALIZED -> error("Session became uninitialized unexpectedly")
            }
        }
    }

    private suspend fun collectUsageInfo(sessionInfo: SessionInfo?, timeElapsedSeconds: Long) {
        val messages = client.getMessages(fromExcl = null, toIncl = lastProcessedMessageId)

        val usageInfo = AgentTurnUsageInfo()

        messages.forEach { msg ->
            if (msg.type == MessageKind.ASSISTANT) {
                usageInfo.toolCallsNumber += msg.toolCalls.size
            }
        }

        usageInfo.price = sessionInfo?.lastTurnCostUsd?.toDouble() ?: 0.0
        usageInfo.time = timeElapsedSeconds

        usageInfoList.add(usageInfo)
    }
}
