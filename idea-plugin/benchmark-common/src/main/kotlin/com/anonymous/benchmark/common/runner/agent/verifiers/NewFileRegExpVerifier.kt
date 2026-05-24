package com.anonymous.benchmark.common.runner.agent.verifiers

import com.anonymous.benchmark.common.schema.Message
import com.anonymous.benchmark.common.utils.ChangeType
import com.anonymous.benchmark.common.utils.getChangedFiles
import com.intellij.openapi.project.Project
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
@SerialName("NewFileRegExpVerifier")
@Suppress("PROVIDED_RUNTIME_TOO_LOW")
data class NewFileRegExpVerifier(
    val regExpPattern: String,
) : Verifier {
    override suspend fun verify(
        project: Project,
        scenarioPath: String,
        chatHistory: List<Message>
    ): VerifierResult {
        val regex = Regex(regExpPattern)
        val newFiles = getChangedFiles(project)
            .filter { it.changeType == ChangeType.NEW }

        val matched = newFiles.firstOrNull { regex.containsMatchIn(it.path) }
        return if (matched != null) {
            VerifierResult.Success
        } else {
            val allNew = if (newFiles.isEmpty()) "<no new files>" else newFiles.joinToString { it.path }
            VerifierResult.Failure("No new files matching pattern '$regExpPattern'. New files found: $allNew")
        }
    }
}
