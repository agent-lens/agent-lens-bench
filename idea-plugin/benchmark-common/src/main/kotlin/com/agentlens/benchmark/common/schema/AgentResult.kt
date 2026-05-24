package com.agentlens.benchmark.common.schema

import com.agentlens.benchmark.common.runner.agent.verifiers.VerifierResult
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
@Suppress("PROVIDED_RUNTIME_TOO_LOW")
data class AgentBenchmarkResults(
    val timestamp: String = "",
    val runInfo: BenchmarkRunInfo? = null,
    val projectsResults: List<AgentProjectResults> = emptyList(),
)

@Serializable
@Suppress("PROVIDED_RUNTIME_TOO_LOW")
data class BenchmarkRunInfo(
    val timestamp: String,
    val experimentName: String,

    // data version
    val datasetHash: String,
    val datasetConfigHash: String,

    // plugin version
    val pluginHash: String,

    // model version
    val modelName: String,
    val providerName: String,
    val modelUrl: String? = null
)

@Serializable
@Suppress("PROVIDED_RUNTIME_TOO_LOW")
data class AgentProjectResults(
    val projectTitle: String,
    val results: List<AgentResult>
)

@Serializable
@Suppress("PROVIDED_RUNTIME_TOO_LOW")
sealed interface AgentResult {
    val scenarioName: String
    val simulatorName: String
    val messagePath: String
    val errors: List<String>
}

@Serializable
@SerialName("SuccessResult")
@Suppress("PROVIDED_RUNTIME_TOO_LOW")
data class AgentSuccessResult(
    override val scenarioName: String,
    override val simulatorName: String,
    override val messagePath: String,
    override val errors: List<String>,
    val taskDescription: String,
    val formalVerificationResult: Int,
    val terminationReason: String,
    val agentBenchTags: List<String>,
    val verifierResults: List<VerifierResult>,
    val agentTracePrompt: String,
    val agentPrice: List<Double>,
    val agentTime: List<Long>,
    val agentInputTokens: List<List<Long>> = emptyList(),
    val agentGenerationTokens: List<List<Long>> = emptyList(),
    val agentReasoningTokens: List<Long?> = emptyList(),
    val agentPromptCacheHitTokens: List<List<Long?>> = emptyList(),
    val agentToolCallsNum: List<Int> = emptyList(),
    val agentMessagesPerTurn: List<Int> = emptyList(),
    val agentInteractionTotalTime: Long? = null,
) : AgentResult

@Serializable
@SerialName("FailureResult")
@Suppress("PROVIDED_RUNTIME_TOO_LOW")
data class AgentFailureResult(
    override val scenarioName: String,
    override val simulatorName: String,
    override val messagePath: String,
    override val errors: List<String>,
    val failureReason: String?,
) : AgentResult
