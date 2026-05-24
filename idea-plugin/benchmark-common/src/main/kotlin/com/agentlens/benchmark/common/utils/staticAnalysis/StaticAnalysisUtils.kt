package com.agentlens.benchmark.common.utils.staticAnalysis

import com.agentlens.benchmark.common.utils.benchCoroutineScope
import com.agentlens.benchmark.common.utils.buildSystem.IdeBuildSystem
import com.intellij.codeInsight.daemon.impl.HighlightInfo
import com.intellij.codeInsight.daemon.impl.MainPassesRunner
import com.intellij.lang.annotation.HighlightSeverity
import com.intellij.openapi.editor.Document
import com.intellij.openapi.fileEditor.FileDocumentManager
import com.intellij.openapi.project.Project
import com.intellij.openapi.vfs.VirtualFile
import com.intellij.profile.codeInspection.InspectionProjectProfileManager
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull
import kotlin.collections.iterator
import kotlin.time.Duration
import kotlin.time.Duration.Companion.milliseconds

data class StaticIdeProblem(
    val file: String,
    val line: Int,
    val column: Int,
    val description: String
)

fun HighlightInfo.toStaticIdeProblem(document: Document): StaticIdeProblem? {
    val filePath = FileDocumentManager.getInstance()
        .getFile(document)
        ?.path
        ?: return null

    val offset = this.startOffset
    if (offset < 0 || offset >= document.textLength) return null

    val zeroBasedLineNumber = document.getLineNumber(offset)
    val zeroBasedColNumber = offset - document.getLineStartOffset(zeroBasedLineNumber)
    val description = this.description ?: this.text

    return StaticIdeProblem(filePath, zeroBasedLineNumber + 1, zeroBasedColNumber + 1, description)
}

object StaticAnalysisUtils {
    val ANALYZE_FILES_MS = 40000.milliseconds
    const val MAX_PROBLEMS = 30

    suspend fun getAnalysisResults(
        project: Project,
        files: List<VirtualFile>,
        severity: SeverityLevel,
        timeout: Duration = ANALYZE_FILES_MS
    ): List<StaticIdeProblem>? =
        getHighlightInfos(project, files, severity, timeout)?.entries?.flatMap { (doc, errors) ->
            errors.mapNotNull { it.toStaticIdeProblem(doc) }
        }

    private suspend fun getHighlightInfos(
        project: Project,
        files: List<VirtualFile>,
        severity: SeverityLevel,
        timeout: Duration = ANALYZE_FILES_MS
    ): Map<Document, List<HighlightInfo>>? {
        IdeBuildSystem.refreshBuildSystemIfRequired(project)

        val isTimeout = CompletableDeferred<Unit>()
        val problems = mutableMapOf<Document, MutableList<HighlightInfo>>()

        project.benchCoroutineScope.launch(Dispatchers.IO) {
            val profile = InspectionProjectProfileManager.getInstance(project).currentProfile
            val runner = MainPassesRunner(project, "Running Static Analysis", profile)
            var counter = 0
            fileLoop@ for (file in files) {
                val fileProblems = FileProblemsProvider
                    .getProblems(project, runner, file, isTimeout)

                for ((document, highlightInfos) in fileProblems) {
                    for (info in highlightInfos) {
                        if (!info.matchesSeverity(severity)) continue

                        if (problems[document] == null) {
                            problems[document] = mutableListOf()
                        }
                        problems[document]!!.add(info)
                        counter++

                        if (counter >= MAX_PROBLEMS) break@fileLoop
                    }
                }
            }

            isTimeout.complete(Unit)
        }

        withTimeoutOrNull(timeout) { isTimeout.await() }
            ?: run {
                isTimeout.complete(Unit)
                return null
            }

        return problems
    }

    private fun HighlightInfo.matchesSeverity(severity: SeverityLevel): Boolean {
        return when (severity) {
            SeverityLevel.ERROR -> this.severity == HighlightSeverity.ERROR
            SeverityLevel.WARNING -> this.severity == HighlightSeverity.ERROR || this.severity == HighlightSeverity.WARNING
        }
    }

    enum class SeverityLevel {
        ERROR,
        WARNING
    }
}


