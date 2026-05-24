package com.agentlens.benchmark.common.runner.agent.verifiers

import com.agentlens.benchmark.common.schema.Message
import com.intellij.openapi.project.Project
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

interface Verifier {
    suspend fun verify(project: Project, scenarioPath: String, chatHistory: List<Message>): VerifierResult
}

@Serializable
@Suppress("PROVIDED_RUNTIME_TOO_LOW")
sealed interface VerifierResult {
    fun isSuccess(): Boolean

    @Serializable
    @SerialName("Success")
    @Suppress("PROVIDED_RUNTIME_TOO_LOW")
    data object Success: VerifierResult {
        override fun isSuccess() = true
    }

    @Serializable
    @SerialName("Failure")
    @Suppress("PROVIDED_RUNTIME_TOO_LOW")
    data class Failure(val message: String) : VerifierResult {
        override fun isSuccess() = false
    }

    @Serializable
    @SerialName("SuccessWithMetrics")
    @Suppress("PROVIDED_RUNTIME_TOO_LOW")
    data class SuccessWithMetrics(
        val metrics: JsonObject
    ): VerifierResult {
        override fun isSuccess() = true
    }
}
