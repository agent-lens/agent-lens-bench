package com.agentlens.benchmark.runner.agent.preprocessor

import com.agentlens.benchmark.common.runner.agent.preprocessor.ScenarioPreprocessor
import com.agentlens.benchmark.common.runner.agent.logger
import com.agentlens.benchmark.common.utils.Left
import com.agentlens.benchmark.common.utils.Right
import com.agentlens.benchmark.common.utils.buildSystem.IdeBuildSystem
import com.agentlens.benchmark.common.utils.getProjectDir
import com.agentlens.benchmark.common.utils.truncateBuildOutput
import com.intellij.openapi.project.Project
import com.intellij.openapi.vfs.toNioPathOrNull
import git4idea.repo.GitRepository
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlin.io.path.pathString

@Serializable
@SerialName("RunBuildSystemTaskPreprocessor")
@Suppress("PROVIDED_RUNTIME_TOO_LOW")
data class RunBuildSystemTaskPreprocessor(
    val buildSystemName: String,
    val tasks: List<String>
): ScenarioPreprocessor {
    override suspend fun prepareProject(project: Project, repo: GitRepository) {
        val projectDir = project.getProjectDir()?.toNioPathOrNull() ?: error("Failed to get project root")

        val buildSystemsProvider = IdeBuildSystem.getInstances().singleOrNull()
            ?: error("Failed to get build system provider")

        val result = buildSystemsProvider.executeTasks(project, buildSystemName, projectDir.pathString, tasks)
        when (result) {
            is Left<Throwable> -> logger.error { "$buildSystemName task execution ($tasks) during preprocessing failed with an error: ${result.failure}" }
            is Right<String> -> logger.info { "Results of $buildSystemName task execution ($tasks) during preprocessing: ```\n${result.value.truncateBuildOutput()}\n```" }
        }
    }
}
