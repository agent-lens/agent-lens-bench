package com.agentlens.benchmark.common.schema

import kotlinx.serialization.Serializable
import java.util.UUID


data class ToolCall(
    val id: String,
    val name: String,
    val arguments: String
)

data class ToolResponse(
    val id: String,
    val name: String,
    val responseData: String,
    /**
     * `false` if the underlying CLI/adapter reported this tool call as an error
     * (e.g. Claude Code `is_error: true`). Mapping of agent-specific error
     * signals into this flag happens in the adapter on the `agent_server` side;
     * here we expose an agent-agnostic boolean. Defaults to `true` for
     * backward compatibility with adapters that do not yet report this flag.
     */
    val success: Boolean = true,
)

@Serializable
enum class MessageKind {
    SYSTEM,
    USER,
    ASSISTANT,
    TOOL
}

data class Message(
    val id: UUID,
    val timestamp: Long?,
    val type: MessageKind,
    val text: String,
    val reasoning: String?,
    val toolCalls: List<ToolCall>,
    val toolResponses: List<ToolResponse>
) {
    companion object {
        fun assistant(
            text: String,
            toolCalls: List<ToolCall> = emptyList(),
            reasoning: String? = null,
        ): Message =
            Message(
                id = UUID.randomUUID(),
                timestamp = null,
                type = MessageKind.ASSISTANT,
                text = text,
                toolCalls = toolCalls,
                toolResponses = emptyList(),
                reasoning = reasoning
            )

        fun tool(
            toolResponses: List<ToolResponse>,
            text: String = ""
        ): Message =
            Message(
                id = UUID.randomUUID(),
                timestamp = null,
                type = MessageKind.TOOL,
                text = text,
                toolCalls = emptyList(),
                reasoning = null,
                toolResponses = toolResponses)

        fun user(text: String): Message =
            Message(
                id = UUID.randomUUID(),
                timestamp = null,
                type = MessageKind.USER,
                text = text,
                toolCalls = emptyList(),
                reasoning = null,
                toolResponses = emptyList()
            )

        fun system(text: String): Message =
            Message(
                id = UUID.randomUUID(),
                timestamp = null,
                type = MessageKind.SYSTEM,
                text = text,
                toolCalls = emptyList(),
                reasoning = null,
                toolResponses = emptyList()
            )
    }
}
