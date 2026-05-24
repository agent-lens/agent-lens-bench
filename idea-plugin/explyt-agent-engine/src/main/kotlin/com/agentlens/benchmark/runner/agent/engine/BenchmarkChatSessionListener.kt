package com.agentlens.benchmark.runner.agent.engine

import com.explyt.benchmark.api.v1.chat.ChatSessionListener
import com.explyt.benchmark.api.v1.chat.ToolCallRecord
import com.explyt.benchmark.api.v1.chat.ToolResponseStatus
import com.agentlens.benchmark.common.schema.Message
import com.agentlens.benchmark.common.schema.MessageKind
import com.agentlens.benchmark.common.schema.ToolCall
import com.agentlens.benchmark.common.schema.ToolCallHistoryEntry
import com.agentlens.benchmark.common.schema.ToolResponse

class BenchmarkChatSessionListener(
    val  chatHistory: MutableList<Message>
): ChatSessionListener {
    val toolResponseHistory: MutableMap<Int, List<ToolCallHistoryEntry>> = mutableMapOf()

    override suspend fun onAgentTurn() {
        chatHistory.add(Message.assistant(""))
    }

    override suspend fun onResponseToken(token: String) {
        val lastMessage = chatHistory.removeLast()
        chatHistory.add(lastMessage.copy(text = lastMessage.text + token))
    }

    override suspend fun onToolCallStarted(toolName: String, toolId: String, arguments: String) {
        val lastMessageIndex = chatHistory.indexOfLast { it.type == MessageKind.ASSISTANT }
        val lastMessage = chatHistory[lastMessageIndex]
        val benchToolCall = ToolCall(toolId, toolName, arguments)
        chatHistory[lastMessageIndex] = lastMessage.copy(toolCalls = lastMessage.toolCalls + benchToolCall)
    }

    override suspend fun onToolCallFinished(toolCallRecord: ToolCallRecord) {
        val toolStatusHeader =
            "Tool Execution Status: ${toolCallRecord.status.name.lowercase()}\nMessage: "
        chatHistory.add(
            Message.tool(
                listOf(
                    ToolResponse(
                        toolCallRecord.id,
                        toolCallRecord.name,
                        toolStatusHeader + toolCallRecord.responseContent
                    )
                )
            )
        )

        val lastMessageIndex = chatHistory.indexOfLast { it.type == MessageKind.ASSISTANT }
        val toolCallHistoryEntry = ToolCallHistoryEntry(
            name = toolCallRecord.name,
            arguments = toolCallRecord.arguments,
            success = toolCallRecord.status == ToolResponseStatus.SUCCESS,
            responseContent = toolCallRecord.responseContent,
            systemReminder = toolCallRecord.systemReminder,
        )

        toolResponseHistory[lastMessageIndex] = toolResponseHistory[lastMessageIndex].orEmpty() + toolCallHistoryEntry
    }
}
