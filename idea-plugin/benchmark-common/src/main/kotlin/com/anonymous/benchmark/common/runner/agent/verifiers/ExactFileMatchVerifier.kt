package com.anonymous.benchmark.common.runner.agent.verifiers

import com.anonymous.benchmark.common.schema.Message
import com.anonymous.benchmark.common.utils.getChangedFiles
import com.anonymous.benchmark.common.utils.getResourceText
import com.anonymous.benchmark.common.utils.resolvePath
import com.anonymous.benchmark.common.utils.normalizeLineEndings
import com.anonymous.benchmark.common.utils.getProjectDir
import com.intellij.openapi.project.Project
import com.intellij.openapi.vfs.toNioPathOrNull
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import java.nio.file.Path
import kotlin.io.path.pathString
import kotlin.io.path.readText

@Serializable
@Suppress("PROVIDED_RUNTIME_TOO_LOW")
data class FileMatch(
    val actualFilePath: String,
    val expectedFilePath: String
)

@Serializable
@SerialName("ExactFileMatchVerifier")
@Suppress("PROVIDED_RUNTIME_TOO_LOW")
data class ExactFileMatchVerifier(
    val fileMatches: List<FileMatch>,
    val ignoreEmptyLines: Boolean = false,
    val trim: Boolean = false,
    val checkOtherFilesUnchanged: Boolean = true,
) : Verifier {
    override suspend fun verify(
        project: Project,
        scenarioPath: String,
        chatHistory: List<Message>
    ): VerifierResult {
        val projectDir = project.getProjectDir()?.toNioPathOrNull() ?: error("Failed to get project root")

        fileMatches.forEach { (actualFilePath, expectedFilePath) ->
            if (!checkFileMatch(actualFilePath, expectedFilePath, scenarioPath, projectDir)) {
                return VerifierResult.Failure("Content of '$actualFilePath' does not exactly match '$expectedFilePath'")
            }
        }

        return if (checkOtherFilesUnchanged) {
            val changedFiles = getExtraChangedFiles(project, projectDir)
            if (changedFiles.isNotEmpty()) {
                VerifierResult.Failure("${changedFiles.size} unexpected files got changed, for example '${changedFiles.first()}'")
            } else {
                VerifierResult.Success
            }
        } else {
            VerifierResult.Success
        }
    }

    private fun checkFileMatch(
        actualFilePath: String,
        expectedFilePath: String,
        scenarioPath: String,
        projectDir: Path,
    ): Boolean {
        val actualPath = resolvePath(projectDir, actualFilePath)
        val actualLines = actualPath
            .readText()
            .let { if (trim) it.trim() else it }
            .normalizeLineEndings()
            .lines()
            .map { it.trimEnd() }

        val fullExpectedFilePath = Path.of(scenarioPath, expectedFilePath).pathString
        val expectedLines = getResourceText(fullExpectedFilePath)
            ?.let { if (trim) it.trim() else it }
            ?.normalizeLineEndings()
            ?.lines()
            ?.map { it.trimEnd() }
            ?: error("Failed to read expected file content at path '$expectedFilePath'")

        return if (ignoreEmptyLines) {
            actualLines.filter { it.isNotBlank() } == expectedLines.filter { it.isNotBlank() }
        } else {
            actualLines == expectedLines
        }
    }

    private fun getExtraChangedFiles(project: Project, projectDir: Path): Set<String> {
        val changed = getChangedFiles(project).map { it.path }.toSet()
        val allowed = fileMatches.map { it.actualFilePath }.toSet()

        val changedNorm = changed.map { projectDir.resolve(Path.of(it)).pathString }.toSet()
        val allowedNorm = allowed.map { projectDir.resolve(Path.of(it)).pathString }.toSet()

        // If any changed file is not in allowed set, fail
        return changedNorm.subtract(allowedNorm)
    }
}
