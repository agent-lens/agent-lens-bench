package com.anonymous.benchmark.common.runner.agent.verifiers

import com.anonymous.benchmark.common.schema.Message
import com.anonymous.benchmark.common.utils.getChangedFiles
import com.anonymous.benchmark.common.utils.getProjectDir
import com.intellij.openapi.project.Project
import com.intellij.openapi.vfs.toNioPathOrNull
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import java.io.File
import java.nio.file.FileSystems
import java.nio.file.Path
import java.nio.file.PathMatcher
import kotlin.io.path.invariantSeparatorsPathString
import kotlin.io.path.relativeTo

@Serializable
@SerialName("NoChangesVerifier")
@Suppress("PROVIDED_RUNTIME_TOO_LOW")
data class NoChangesVerifier(
    val allowedFiles: List<String> = emptyList(),
    val allowedGlobs: List<String> = emptyList(),
    val forbiddenGlobs: List<String> = emptyList(),
) : Verifier {
    override suspend fun verify(
        project: Project,
        scenarioPath: String,
        chatHistory: List<Message>
    ) =
        with(project.projectDirPath()) {
            val changedFiles = project.changedFilesRelative(this)
            val allowedFileSet = normalizeRelativePaths(allowedFiles)
            val allowedMatchers = allowedGlobs.toGlobMatchers()
            val forbiddenMatchers = forbiddenGlobs.toGlobMatchers()

            changedFiles
                .filterNot { file ->
                    isAllowedChange(
                        file = file,
                        allowedFiles = allowedFileSet,
                        allowedMatchers = allowedMatchers,
                        forbiddenMatchers = forbiddenMatchers,
                    )
                }
                .toSet()
                .toVerifierResult { file, count -> "$count unexpected files changed, e.g. '$file'" }
        }
}

@Serializable
@SerialName("YesChangesVerifier")
@Suppress("PROVIDED_RUNTIME_TOO_LOW")
data class YesChangesVerifier(
    val targetFiles: List<String> = emptyList(),
    val targetGlobs: List<String> = emptyList(),
) : Verifier {
    override suspend fun verify(
        project: Project,
        scenarioPath: String,
        chatHistory: List<Message>
    ) =
        with(project.projectDirPath()) {
            val changedFiles = project.changedFilesRelative(this)
            val targetFileSet = normalizeRelativePaths(targetFiles)
            val targetMatchers = targetGlobs.toGlobMatchers()

            buildSet {
                addAll(targetFileSet.filterNot(changedFiles::contains))

                targetGlobs.forEachIndexed { index, pattern ->
                    if (changedFiles.none { file -> targetMatchers[index].matches(pathOf(file)) }) {
                        add(pattern)
                    }
                }
            }.toVerifierResult { file, count -> "$count target files not changed, e.g. '$file'" }
        }
}

private fun Project.projectDirPath(): Path =
    getProjectDir()?.toNioPathOrNull() ?: error("Failed to get project root")

private fun Path.normalizeRelativePaths(paths: List<String>): Set<String> =
    paths.mapTo(linkedSetOf()) { normalizeRelativePath(it) }

private fun Path.normalizeRelativePath(path: String): String =
    resolve(path)
        .normalize()
        .relativeTo(normalize())
        .invariantSeparatorsPathString

private fun Project.changedFilesRelative(projectDir: Path): Set<String> =
    getChangedFiles(this)
        .mapTo(linkedSetOf()) { changedFile ->
            projectDir.normalizeRelativePath(changedFile.path)
        }

private fun isAllowedChange(
    file: String,
    allowedFiles: Set<String>,
    allowedMatchers: List<PathMatcher>,
    forbiddenMatchers: List<PathMatcher>,
): Boolean {
    val path = pathOf(file)

    if (forbiddenMatchers.any { matcher -> matcher.matches(path) }) {
        return false
    }

    val hasAllowRules = allowedFiles.isNotEmpty() || allowedMatchers.isNotEmpty()
    if (!hasAllowRules) {
        return true
    }

    if (file in allowedFiles) {
        return true
    }

    return allowedMatchers.any { matcher -> matcher.matches(path) }
}

private fun List<String>.toGlobMatchers(): List<PathMatcher> =
    map { pattern ->
        FileSystems.getDefault().getPathMatcher("glob:${normalizeGlobPattern(pattern)}")
    }

private fun normalizeGlobPattern(pattern: String): String =
    pattern.replace('\\', '/')

private fun pathOf(path: String): Path =
    Path.of(path.replace('/', File.separatorChar))

private inline fun Set<String>.toVerifierResult(message: (example: String, count: Int) -> String): VerifierResult =
    firstOrNull()
        ?.let { VerifierResult.Failure(message(it, size)) }
        ?: VerifierResult.Success
