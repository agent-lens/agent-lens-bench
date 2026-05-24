@file:Suppress("PROVIDED_RUNTIME_TOO_LOW")
package com.anonymous.benchmark.common.runner.agent.engine

import com.anonymous.benchmark.common.schema.Message
import kotlinx.serialization.Serializable
import java.util.*

@Serializable
enum class SessionState {
    UNINITIALIZED, // i.e. agent is starting (launching Claude Code CLI etc)
    READY, // agent is ready to receive user message
    BUSY, // agent is working
}

@Serializable
data class SessionInfo(
    @Serializable(with = UUIDSerializer::class)
    val id: UUID,
    val state: SessionState,
    @Serializable(with = UUIDSerializer::class)
    val lastMessageId: UUID?,
    val timeout: Boolean,
    val error: String? = null,
    val errorTimestamp: Long? = null,
    val lastTurnCostUsd: Float? = null,
)

@Serializable
data class McpServerConfig(
    val type: String,
    val url: String,
    val headers: Map<String, String>
)

@Serializable
data class ClientAgentSettings(
    val modelName: String,
    val mcpServers: Map<String, McpServerConfig>
)

interface AgentEngineClient {

    /**
     * Starts launching the new agent session with projectPath as working dir
     */
    suspend fun newSession(
        agentSettings: ClientAgentSettings,
        projectPath: String,
        initialHistory: List<Message>
    ): SessionInfo

    /**
     * Used to ping for the current status to understand if new message can be sumbitted
     */
    suspend fun getSessionInfo(id: UUID): SessionInfo

    /**
     * Navigates the message history
     */
    suspend fun getMessages(fromExcl: UUID?, toIncl: UUID?): List<Message>

    /**
     * Adds a new user message to history and makes an agent start working on it
     *
     * Valid only if the current state is ready, else returns error
     */
    suspend fun submitUserMessage(content: String, timeoutMillis: Long?)

    /**
     * Returns a raw JSON dump of chat. Returned as raw payload
     */
    suspend fun getRawChatDump(id: UUID): String
}
