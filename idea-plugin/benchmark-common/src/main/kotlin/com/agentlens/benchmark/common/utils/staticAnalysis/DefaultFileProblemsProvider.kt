package com.agentlens.benchmark.common.utils.staticAnalysis

import com.intellij.codeInsight.daemon.impl.HighlightInfo
import com.intellij.codeInsight.daemon.impl.MainPassesRunner
import com.intellij.openapi.editor.Document
import com.intellij.openapi.progress.ProgressManager
import com.intellij.openapi.progress.util.ProgressIndicatorBase
import com.intellij.openapi.project.Project
import com.intellij.openapi.util.Computable
import com.intellij.openapi.vfs.InvalidVirtualFileAccessException
import com.intellij.openapi.vfs.VirtualFile
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

object DefaultFileProblemsProvider : FileProblemsProvider {
    private val mainPassesMutex = Mutex()

    override suspend fun getProblems(
        project: Project,
        runner: MainPassesRunner,
        file: VirtualFile,
        isTimeout: CompletableDeferred<Unit>,
    ): Map<Document, List<HighlightInfo>> = withContext(Dispatchers.IO + NonCancellable) {
        mainPassesMutex.withLock {
            if (isTimeout.isCompleted) {
                return@withContext emptyMap()
            }

            ProgressManager.getInstance().runProcess(
                Computable {
                    if (file.isValid) {
                        try {
                            runner.runMainPasses(listOf(file))
                        } catch (_: InvalidVirtualFileAccessException) {
                            // The file got invalid while running main passes
                            emptyMap()
                        }
                    } else {
                        emptyMap()
                    }
                },
                ProgressIndicatorBase(),
            )
        }
    }
}
