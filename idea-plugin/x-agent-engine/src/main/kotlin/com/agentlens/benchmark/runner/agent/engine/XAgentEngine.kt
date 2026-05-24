package com.agentlens.benchmark.runner.agent.engine

import com.x.benchmark.api.v1.chat.AgentType
import com.x.benchmark.api.v1.chat.ChatSession
import com.x.benchmark.api.v1.chat.ChatSessionFactory
import com.agentlens.benchmark.common.schema.Message
import com.x.benchmark.api.v1.llm.LlmConfigurationService
import com.x.benchmark.api.v1.llm.LlmProviderConfig
import com.x.benchmark.api.v1.llm.ProviderName
import com.x.benchmark.api.v1.mcp.HttpMcpServerConfig
import com.x.benchmark.api.v1.mcp.McpManagementService
import com.agentlens.benchmark.common.dialogs.ModelSettings
import com.agentlens.benchmark.common.runner.agent.AgentEnvService
import com.agentlens.benchmark.common.runner.agent.AgentTurnUsageInfo
import com.agentlens.benchmark.common.runner.agent.EnvVariable
import com.agentlens.benchmark.common.runner.agent.engine.AgentEngine
import com.agentlens.benchmark.common.schema.AgentScenarioSettings
import com.agentlens.benchmark.common.schema.BenchHttpMcpServerConfiguration
import com.agentlens.benchmark.common.schema.MessageToolCalls
import com.agentlens.benchmark.common.schema.ScenarioLanguage
import com.agentlens.benchmark.common.schema.ToolCallHistoryEntry
import com.agentlens.benchmark.common.schema.UserRequest
import com.intellij.openapi.project.Project
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.Transient
import kotlin.collections.component1
import kotlin.collections.component2


@Serializable
@Suppress("PROVIDED_RUNTIME_TOO_LOW")
abstract class XAgentEngine: AgentEngine {
    abstract val agentType: AgentType

    override fun getAgentName(): String = "X"

    @Transient
    private lateinit var benchmarkListener: BenchmarkChatSessionListener

    @Transient
    private lateinit var chatSession: ChatSession

    override suspend fun initModelProviderBeforeBenchmarkRun(settings: ModelSettings): String {
        val modelConfig = LlmProviderConfig(
            ProviderName.values().firstOrNull { it.value == settings.providerName }
                ?: error("Could not find valid provider with name \"${settings.providerName}\""),
            settings.modelName,
            apiKey = AgentEnvService.getEnvValue(EnvVariable.AGENT_API_KEY) ?: "",
            settings.modelUrl
        )
        val modelName = LlmConfigurationService.getInstance().configureModel(modelConfig)
        return modelName
    }

    override suspend fun initBeforeBenchmarkRun() {
        McpManagementService.getInstance().disableAutoConnect()
    }

    private suspend fun initMcpServersBeforeScenarioRun(mcpServers: List<BenchHttpMcpServerConfiguration>) {
        val servers = mcpServers.map {
            HttpMcpServerConfig(
                name = it.name,
                url = it.url,
                headers = it.headers
            )
        }
        McpManagementService.getInstance().configureServers(servers)
    }

    override suspend fun initBeforeScenarioRun(
        project: Project,
        chatHistory: MutableList<Message>,
        agentSettings: AgentScenarioSettings,
    ) {
        initScenarioPromptLanguage(agentSettings.scenarioLanguage)
        initMcpServersBeforeScenarioRun(agentSettings.mcpServers)

        benchmarkListener = BenchmarkChatSessionListener(chatHistory)
        chatSession = ChatSessionFactory
            .getInstance(project)
            .createSession(agentType, benchmarkListener)
    }

    private fun initScenarioPromptLanguage(language: ScenarioLanguage) {
        val pluginLang = when (language) {
            ScenarioLanguage.English -> com.x.benchmark.api.v1.llm.PromptLanguage.English
            ScenarioLanguage.Russian -> com.x.benchmark.api.v1.llm.PromptLanguage.Russian
            ScenarioLanguage.Chinese -> com.x.benchmark.api.v1.llm.PromptLanguage.Chinese
        }
        LlmConfigurationService.getInstance().setPromptLanguage(pluginLang)
    }

    override suspend fun sendRequestWithTimeout(request: UserRequest, timeoutSeconds: Long) {
        chatSession.send(request.prompt, timeoutSeconds)
    }

    override fun getUsages(): List<AgentTurnUsageInfo> {
        return chatSession.getUsages().map {
            AgentTurnUsageInfo().apply {
                price = it.price
                time = it.timeSeconds
                toolCallsNumber = it.toolCallsNumber

                inputTokens.addAll(it.inputTokens)
                generationTokens.addAll(it.generationTokens)
                promptCacheHitTokens.addAll(it.promptCacheHitTokens)
            }
        }
    }

    override suspend fun getChatDump(): String {
        return chatSession.getChatDump()
    }

    override suspend fun getToolCallsDump(): List<MessageToolCalls> {
        return benchmarkListener.toolResponseHistory
            .map { (messageIndex, toolCalls) ->
                MessageToolCalls(
                    assistantMessageIndex = messageIndex,
                    calls = toolCalls.map {
                        ToolCallHistoryEntry(
                            name = it.name,
                            arguments = it.arguments,
                            success = it.success,
                            responseContent = it.responseContent,
                            systemReminder = it.systemReminder,
                        )
                    }
                )
            }
    }

    override fun forceTerminateScenarioRun() {
        chatSession.forceClose()
    }
}

@Serializable
@SerialName("XCommonAgentEngine")
@Suppress("PROVIDED_RUNTIME_TOO_LOW")
class XDefaultAgentEngine : XAgentEngine() {
    override val agentType: AgentType = AgentType.Default
}
