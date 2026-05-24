package com.anonymous.benchmark.common.runner.agent.verifiers

import com.anonymous.benchmark.common.schema.Message
import com.anonymous.benchmark.common.schema.MessageKind
import com.intellij.openapi.project.Project
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
@SerialName("ChatRegExpCountVerifier")
@Suppress("PROVIDED_RUNTIME_TOO_LOW")
data class ChatRegExpCountVerifier(
    val regExpPattern: String,
    val strictCount: Boolean,
    val numExpected: Int = 1,
) : Verifier {
    override suspend fun verify(
        project: Project,
        scenarioPath: String,
        chatHistory: List<Message>
    ): VerifierResult {
        val regExp = Regex(regExpPattern)
        val count = chatHistory
            .filter { it.type == MessageKind.ASSISTANT  }
            .map { it.text }
            .sumOf { regExp.findAll(it).count() }
        return if (count == numExpected || (!strictCount && count >= numExpected)) {
            VerifierResult.Success
        } else {
            VerifierResult.Failure("Expected ${if (strictCount) "exactly" else "at least"} $numExpected matches of '$regExpPattern' in chat history, but got $count")
        }
    }
}
