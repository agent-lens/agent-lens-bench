package com.anonymous.benchmark.utils

import com.anonymous.benchmark.common.utils.getProjectDir
import com.intellij.openapi.application.readAction
import com.intellij.openapi.project.Project
import com.intellij.openapi.vfs.resolveFromRootOrRelative
import com.intellij.psi.PsiClass
import com.intellij.psi.PsiJavaFile
import com.intellij.psi.PsiManager
import com.intellij.psi.PsiMethod
import com.intellij.psi.util.ClassUtil
import org.jetbrains.kotlin.asJava.toLightClass
import org.jetbrains.kotlin.psi.KtClassOrObject
import org.jetbrains.kotlin.psi.KtFile

suspend fun Project.resolvePsiClass(
    relativePath: String,
    fullyQualifiedName: String,
): PsiClass? {
    return readAction {
        val containingVirtualFile = getProjectDir()
            ?.resolveFromRootOrRelative(relativePath)
            ?: return@readAction null
        val psiFile =
            PsiManager.getInstance(this)
                .findFile(containingVirtualFile)
                ?: return@readAction null
        return@readAction when (psiFile) {
            is PsiJavaFile ->
                psiFile.classes
                    .singleOrNull { it.qualifiedName == fullyQualifiedName }

            is KtFile ->
                psiFile.declarations
                    .filterIsInstance<KtClassOrObject>()
                    .singleOrNull { it.fqName?.asString() == fullyQualifiedName }
                    ?.toLightClass()

            else -> null
        }
    }
}

suspend fun PsiClass.resolvePsiMethods(
    methodName: String,
    methodSignature: String?,
): Set<PsiMethod> {
    val methods = findMethodsByName(methodName, false).toSet()
    if (methodSignature == null || methods.size <= 1) {
        return methods
    }
    return methods.filter {
        ClassUtil.getVMParametersMethodSignature(it) == methodSignature
    }.toSet()
}
