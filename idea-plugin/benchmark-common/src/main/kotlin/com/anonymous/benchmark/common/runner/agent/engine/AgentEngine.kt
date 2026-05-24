package com.anonymous.benchmark.common.runner.agent.engine

import com.anonymous.benchmark.common.schema.Message
import com.anonymous.benchmark.common.dialogs.ModelSettings
import com.anonymous.benchmark.common.runner.agent.AgentTurnUsageInfo
import com.anonymous.benchmark.common.schema.AgentScenarioSettings
import com.anonymous.benchmark.common.schema.MessageToolCalls
import com.anonymous.benchmark.common.schema.UserRequest
import com.intellij.openapi.project.Project

@Suppress("PROVIDED_RUNTIME_TOO_LOW")
interface AgentEngine {
    fun getAgentName(): String

    /**
     * Setups model provider from settings
     *
     * @return - model name
     */
    suspend fun initModelProviderBeforeBenchmarkRun(settings: ModelSettings): String
    suspend fun initBeforeBenchmarkRun() {}
    suspend fun initBeforeScenarioRun(project: Project, chatHistory: MutableList<Message>, agentSettings: AgentScenarioSettings)

    suspend fun sendRequestWithTimeout(request: UserRequest, timeoutSeconds: Long)

    fun forceTerminateScenarioRun()

    fun getUsages(): List<AgentTurnUsageInfo>
    suspend fun getChatDump(): String
    suspend fun getToolCallsDump(): List<MessageToolCalls>
}
