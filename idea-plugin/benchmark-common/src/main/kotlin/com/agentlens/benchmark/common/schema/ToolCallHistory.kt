@file:Suppress("PROVIDED_RUNTIME_TOO_LOW")
package com.agentlens.benchmark.common.schema

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class MessageToolCalls(
    @SerialName("assistant_message_index")
    val assistantMessageIndex: Int,
    @SerialName("calls")
    val calls: List<ToolCallHistoryEntry>
)

@Serializable
data class ToolCallHistoryEntry(
    @SerialName("name")
    val name: String,
    @SerialName("arguments")
    val arguments: String,
    @SerialName("success")
    val success: Boolean,
    @SerialName("response_content")
    val responseContent: String,
    @SerialName("system_reminder")
    val systemReminder: String
)
