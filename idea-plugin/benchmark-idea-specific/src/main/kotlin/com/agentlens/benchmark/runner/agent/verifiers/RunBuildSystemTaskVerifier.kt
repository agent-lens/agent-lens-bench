package com.agentlens.benchmark.runner.agent.verifiers

import com.agentlens.benchmark.common.schema.Message
import com.agentlens.benchmark.common.runner.agent.verifiers.Verifier
import com.agentlens.benchmark.common.runner.agent.verifiers.VerifierResult
import com.agentlens.benchmark.common.runner.agent.logger
import com.agentlens.benchmark.common.utils.resolvePath
import com.agentlens.benchmark.common.utils.Left
import com.agentlens.benchmark.common.utils.Right
import com.agentlens.benchmark.common.utils.buildSystem.IdeBuildSystem
import com.agentlens.benchmark.common.utils.getProjectDir
import com.agentlens.benchmark.common.utils.truncateBuildOutput
import com.intellij.openapi.project.Project
import com.intellij.openapi.vfs.toNioPathOrNull
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlin.io.path.pathString

@Serializable
@SerialName("RunBuildSystemTaskVerifier")
@Suppress("PROVIDED_RUNTIME_TOO_LOW")
data class RunBuildSystemTaskVerifier(
    val buildSystemName: String,
    val tasks: List<String>,
    val path: String = ".",
    val regExpPattern: String? = null,
    val strictCount: Boolean = true,
    val numExpected: Int = 1,
) : Verifier {
    override suspend fun verify(
        project: Project,
        scenarioPath: String,
        chatHistory: List<Message>
    ): VerifierResult {
        val projectDir = project.getProjectDir()?.toNioPathOrNull() ?: error("Failed to get project root")
        val targetPath = if (path.isBlank()) projectDir else resolvePath(projectDir, path)

        val buildSystemsProvider = IdeBuildSystem.getInstances().singleOrNull()
            ?: error("Failed to get build system provider")

        val result = buildSystemsProvider.executeTasks(project, buildSystemName, targetPath.pathString, tasks)
        when (result) {
            is Left<Throwable> -> error("$buildSystemName task execution ($tasks) during verification failed with an error: ${result.failure}")
            is Right<String> -> logger.warn { "Results of $buildSystemName task execution ($tasks) during verification: ```\n${result.value.truncateBuildOutput()}\n```" }
        }

        if (regExpPattern == null) {
            return VerifierResult.Success
        }

        val regExp = Regex(regExpPattern)
        val count = regExp.findAll((result as Right<String>).value).count()
        return if (count == numExpected || (!strictCount && count > numExpected)) {
            VerifierResult.Success
        } else {
            VerifierResult.Failure("Expected ${if (strictCount) "exactly" else "at least"} $numExpected matches of '$regExpPattern' in $buildSystemName tasks ($tasks) output, but got $count")
        }
    }
}
