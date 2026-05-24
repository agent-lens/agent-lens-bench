package com.anonymous.benchmark.common.utils

import com.intellij.openapi.project.Project
import com.intellij.openapi.vfs.LocalFileSystem
import com.intellij.openapi.vfs.VfsUtil
import com.intellij.openapi.vfs.VirtualFile
import com.intellij.openapi.vfs.toNioPathOrNull
import com.intellij.psi.PsiFile
import com.intellij.psi.PsiManager
import java.nio.file.Path
import java.nio.file.Paths
import kotlin.io.path.Path

fun getResourceText(filePath: String): String? {
    class Dummy
    val normalizedFilePath = filePath.replace('\\', '/')
    return Dummy::class.java.classLoader.getResourceAsStream(normalizedFilePath)?.bufferedReader()?.use { it.readText() }
}

fun resolvePath(base: Path, pathStr: String): Path {
    val p = Paths.get(pathStr)
    return if (p.isAbsolute) p else base.resolve(p)
}

fun collectPsiFiles(project: Project, root: Path, recursive: Boolean): List<PsiFile> {
    val virtualRoot = VfsUtil.findFile(root, true) ?: return emptyList()
    val psiManager = PsiManager.getInstance(project)
    val result = mutableListOf<PsiFile>()

    fun visit(dirOrFile: VirtualFile) {
        if (dirOrFile.isDirectory) {
            if (!recursive && dirOrFile != virtualRoot) return
            dirOrFile.children?.forEach { child ->
                visit(child)
            }
        } else {
            psiManager.findFile(dirOrFile)?.let { result.add(it) }
        }
    }

    visit(virtualRoot)
    return result
}

fun Project.getProjectDir(): VirtualFile? {
    return basePath?.let {
        LocalFileSystem.getInstance().findFileByPath(it)
    }
}

fun getProjectDir(project: Project) =
    project.getProjectDir()?.toNioPathOrNull() ?: error("Failed to get project root")


fun String.isAbsolutePath(): Boolean {
    return try {
        Path(this).isAbsolute
    } catch (_: Throwable) {
        false
    }
}

fun Project.findVirtualFileInTheProject(pathInProject: String): VirtualFile? {
    val projectDir = getProjectDir() ?: return null
    val projectPath = projectDir.path

    if (pathInProject.isAbsolutePath()) {
        return if (pathInProject.startsWith(projectPath)) {
            LocalFileSystem.getInstance().findFileByPath(pathInProject)
        } else {
            null
        }
    }

    return LocalFileSystem.getInstance().findFileByPath(
        Paths.get(projectPath, pathInProject).normalize().toString()
    ) ?: projectDir.findFileByRelativePath(pathInProject)
}

