package com.agentlens.benchmark.common.runner.agent.verifiers

import com.agentlens.benchmark.common.schema.Message
import com.agentlens.benchmark.common.utils.resolvePath
import com.agentlens.benchmark.common.utils.getProjectDir
import com.intellij.openapi.project.Project
import com.intellij.openapi.vfs.toNioPathOrNull
import kotlinx.serialization.Serializable
import kotlin.io.path.extension
import kotlin.io.path.isDirectory
import kotlin.io.path.isRegularFile
import kotlin.io.path.readText
import kotlin.io.path.walk

@Serializable
@Suppress("PROVIDED_RUNTIME_TOO_LOW")
abstract class AbstractFileRegExpCountVerifier(): Verifier {
    abstract val regExpPattern: String
    abstract val searchIn: String
    abstract val strictCount: Boolean
    abstract val numExpected: Int
    abstract val uncommentedOnly: Boolean

    abstract fun removeCommented(fileText: String): String
    abstract val ignoredExtensions: List<String>

    @OptIn(kotlin.io.path.ExperimentalPathApi::class)
    override suspend fun verify(
        project: Project,
        scenarioPath: String,
        chatHistory: List<Message>
    ): VerifierResult {
        val regExp = Regex(regExpPattern)
        val projectDir = project.getProjectDir()?.toNioPathOrNull() ?: error("Failed to get project root")
        val target = if (searchIn.isBlank()) projectDir else resolvePath(projectDir, searchIn)

        val count = when {
            target.isDirectory() -> target.walk()
                .filter { it.isRegularFile() && it.extension !in ignoredExtensions }
                .map { file -> if (uncommentedOnly) removeCommented(file.readText()) else file.readText() }
                .map { fileText -> regExp.findAll(fileText).count() }
                .sum()
            target.isRegularFile() -> {
                val text = target.readText()
                val processed = if (uncommentedOnly) removeCommented(text) else text
                regExp.findAll(processed).count()
            }
            else -> return VerifierResult.Failure("Target path '$searchIn' does not exist")
        }
        return if (count == numExpected || (!strictCount && count >= numExpected)) {
            VerifierResult.Success
        } else {
            VerifierResult.Failure("Expected ${if (strictCount) "exactly" else "at least"} $numExpected matches of '$regExpPattern' in '$searchIn', but got $count")
        }
    }
}
