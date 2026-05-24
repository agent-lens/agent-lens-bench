package com.agentlens.benchmark.common.schema

import com.agentlens.benchmark.common.runner.agent.engine.AgentEngine
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
@SerialName("AgentConfig")
@Suppress("PROVIDED_RUNTIME_TOO_LOW")
data class AgentConfig(
    val budgetDollarsLimit: Float,
    val defaultBranch: String,
    val defaultRepoHash: String,
    val agentEngine: AgentEngine,
    val scenarioPaths: List<String>,
    val userPaths: List<String>,
)
