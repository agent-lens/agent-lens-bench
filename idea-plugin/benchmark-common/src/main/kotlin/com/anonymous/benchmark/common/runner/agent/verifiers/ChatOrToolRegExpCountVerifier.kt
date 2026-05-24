package com.anonymous.benchmark.common.runner.agent.verifiers

import com.anonymous.benchmark.common.schema.Message
import com.anonymous.benchmark.common.schema.MessageKind
import com.intellij.openapi.project.Project
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
@SerialName("ChatOrToolRegExpCountVerifier")
@Suppress("PROVIDED_RUNTIME_TOO_LOW")
data class ChatOrToolRegExpCountVerifier(
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
            .filter { it.type == MessageKind.ASSISTANT || it.type == MessageKind.TOOL }
            .flatMap { msg -> listOf(msg.text) + msg.toolCalls.map { it.arguments } + msg.toolResponses.map { it.responseData } }
            .sumOf { regExp.findAll(it).count() }
        return if (count == numExpected || (!strictCount && count > numExpected)) {
            VerifierResult.Success
        } else {
            VerifierResult.Failure("Expected ${if (strictCount) "exactly" else "at least"} $numExpected matches of '$regExpPattern' in chat or tools history, but got $count")
        }
    }
}
