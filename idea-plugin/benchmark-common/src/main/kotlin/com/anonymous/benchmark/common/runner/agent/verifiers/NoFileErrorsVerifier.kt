package com.anonymous.benchmark.common.runner.agent.verifiers

import com.anonymous.benchmark.common.schema.Message
import com.anonymous.benchmark.common.utils.collectPsiFiles
import com.anonymous.benchmark.common.utils.resolvePath
import com.anonymous.benchmark.common.utils.staticAnalysis.StaticAnalysisUtils
import com.anonymous.benchmark.common.utils.staticAnalysis.StaticAnalysisUtils.SeverityLevel
import com.anonymous.benchmark.common.utils.findVirtualFileInTheProject
import com.intellij.openapi.application.runReadAction
import com.anonymous.benchmark.common.utils.getProjectDir
import com.intellij.openapi.project.Project
import com.intellij.openapi.vfs.toNioPathOrNull
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlin.io.path.isDirectory
import kotlin.io.path.isRegularFile
import kotlin.io.path.pathString

@Serializable
@Suppress("PROVIDED_RUNTIME_TOO_LOW")
@SerialName("NoFileErrorsVerifier")
class NoFileErrorsVerifier(val path: String, val includeWarnings: Boolean = false, val languages: List<String>) : Verifier {
    override suspend fun verify(
        project: Project,
        scenarioPath: String,
        chatHistory: List<Message>
    ): VerifierResult {
        val projectDir = project.getProjectDir()?.toNioPathOrNull() ?: error("Failed to get project root")
        val target = if (path.isBlank()) projectDir else resolvePath(projectDir, path)

        val errors = when {
            target.isDirectory() -> runReadAction { collectPsiFiles(project, target, true) }
                .filter { file -> languages.any { it.equals(file.language.id, ignoreCase = true) } }
                .mapNotNull { file -> file.virtualFile }
                .let { files ->
                    StaticAnalysisUtils.getAnalysisResults(
                        project = project,
                        files = files,
                        severity = if (includeWarnings) SeverityLevel.WARNING else SeverityLevel.ERROR
                    )
                }

            target.isRegularFile() -> {
                val virtualFile = project.findVirtualFileInTheProject(target.pathString)
                    ?: return VerifierResult.Failure("Could not find virtual file at path '${target.pathString}'")
                StaticAnalysisUtils.getAnalysisResults(
                    project = project,
                    files = listOf(virtualFile),
                    severity = if (includeWarnings) SeverityLevel.WARNING else SeverityLevel.ERROR
                )
            }

            else -> return VerifierResult.Failure("Target path '$path' does not exist")
        } ?: error("Static analysis at '$path' failed")

        return if (errors.isEmpty()) {
            VerifierResult.Success
        } else {
            VerifierResult.Failure("Found ${errors.size} ${if (includeWarnings) "errors or warnings" else "errors"} at '${path}'")
        }
    }
}
