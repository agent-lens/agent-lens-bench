package com.anonymous.benchmark.common.schema

import kotlinx.serialization.Serializable

@Serializable
@Suppress("PROVIDED_RUNTIME_TOO_LOW")
data class AgentBenchMessage(
    val role: String,
    val content: String,
)

@Serializable
@Suppress("PROVIDED_RUNTIME_TOO_LOW")
data class AgentBenchResponse (
    val role: String,
    val request: List<AgentBenchMessage>,
    val response: AgentBenchMessage,
    val responsePrice: Double,
    val responseTime: Long,
)
