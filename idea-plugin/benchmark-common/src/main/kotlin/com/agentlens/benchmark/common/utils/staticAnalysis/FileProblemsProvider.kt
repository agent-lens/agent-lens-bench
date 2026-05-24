package com.agentlens.benchmark.common.utils.staticAnalysis

import com.intellij.codeInsight.daemon.impl.HighlightInfo
import com.intellij.codeInsight.daemon.impl.MainPassesRunner
import com.intellij.openapi.editor.Document
import com.intellij.openapi.extensions.ExtensionPointName
import com.intellij.openapi.project.Project
import com.intellij.openapi.vfs.VirtualFile
import kotlinx.coroutines.CompletableDeferred
import kotlin.collections.iterator

interface FileProblemsProvider {
    suspend fun getProblems(
        project: Project,
        runner: MainPassesRunner,
        file: VirtualFile,
        isTimeout: CompletableDeferred<Unit>,
    ): Map<Document, List<HighlightInfo>>

    companion object {
        private val EP_NAME = ExtensionPointName.create<FileProblemsProvider>("com.agentlens.benchmark.common.fileProblemsProvider")

        private fun getProblemProvider(): FileProblemsProvider {
            return EP_NAME.extensions.singleOrNull() ?: DefaultFileProblemsProvider
        }

        suspend fun getProblems(
            project: Project,
            runner: MainPassesRunner,
            file: VirtualFile,
            isTimeout: CompletableDeferred<Unit>,
        ): Map<Document, List<HighlightInfo>> {
            val result = mutableMapOf<Document, List<HighlightInfo>>()

            if (isTimeout.isCompleted) {
                return result
            }

            val problems = getProblemProvider().getProblems(project, runner, file, isTimeout)
            for ((doc, highlights) in problems) {
                result[doc] = highlights
            }

            return result
        }
    }
}
