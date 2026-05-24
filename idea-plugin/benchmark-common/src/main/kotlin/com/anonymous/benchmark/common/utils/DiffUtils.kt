package com.anonymous.benchmark.common.utils

import com.intellij.openapi.project.Project
import com.intellij.openapi.vcs.changes.Change
import com.intellij.openapi.vcs.changes.ChangeListManager
import com.intellij.openapi.vfs.isFile
import com.intellij.openapi.vfs.toNioPathOrNull
import kotlin.io.path.Path
import kotlin.io.path.readText

data class CodeDiff(
    val path: String,
    val content: String
)

enum class ChangeType {
    MODIFIED,
    NEW,
    DELETED,
    MOVED
}

data class ChangedFile(
    val path: String,
    val changeType: ChangeType,
    val beforeContent: String?,
    val afterContent: String?,
    val beforePath: String? = null,
    val afterPath: String? = null,
)

fun getChangedFiles(project: Project): List<ChangedFile> {
    val projectDir = project.getProjectDir()?.toNioPathOrNull()
        ?: error("Failed to get project root directory for project ${project.name}")

    return ChangeListManager.getInstance(project).allChanges
        .filter { it.virtualFile?.isFile == true }
        .mapNotNull { change ->
            val absolutePath = change.virtualFile?.path ?: return@mapNotNull null
            val relativePath = projectDir.relativize(Path(absolutePath)).toString()

            when (change.type) {
                Change.Type.MODIFICATION -> {
                    val beforeContent = change.beforeRevision?.content
                    val afterContent = change.afterRevision?.content ?: Path(absolutePath).readText()

                    ChangedFile(
                        path = relativePath,
                        changeType = ChangeType.MODIFIED,
                        beforeContent = beforeContent,
                        afterContent = afterContent,
                    )
                }

                Change.Type.NEW -> {
                    val afterContent = change.afterRevision?.content ?: Path(absolutePath).readText()
                    ChangedFile(
                        path = relativePath,
                        changeType = ChangeType.NEW,
                        beforeContent = null,
                        afterContent = afterContent,
                    )
                }

                Change.Type.DELETED -> {
                    val beforeContent = change.beforeRevision?.content
                    ChangedFile(
                        path = relativePath,
                        changeType = ChangeType.DELETED,
                        beforeContent = beforeContent,
                        afterContent = null,
                    )
                }

                Change.Type.MOVED -> {
                    val beforePath = change.beforeRevision?.file?.path
                    val afterPath = change.afterRevision?.file?.path ?: change.virtualFile?.path

                    val beforeContent = change.beforeRevision?.content
                    val afterContent = change.afterRevision?.content ?: afterPath?.let { Path(it).readText() }

                    val beforeRel = projectDir.relativize(Path(beforePath ?: "")).toString()
                    val afterRel = projectDir.relativize(Path(afterPath ?: "")).toString()

                    ChangedFile(
                        path = afterRel,
                        changeType = ChangeType.MOVED,
                        beforeContent = beforeContent,
                        afterContent = afterContent,
                        beforePath = beforeRel,
                        afterPath = afterRel,
                    )
                }
            }
        }
}
