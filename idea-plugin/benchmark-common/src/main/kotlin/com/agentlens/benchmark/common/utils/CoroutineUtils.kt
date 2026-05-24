package com.agentlens.benchmark.common.utils

import com.intellij.openapi.components.Service
import com.intellij.openapi.components.service
import com.intellij.openapi.project.Project
import kotlinx.coroutines.CoroutineScope


val Project.benchCoroutineScope get() = BenchProjectScopeHolder.getInstance(this).coroutineScope

@Service(Service.Level.PROJECT)
class BenchProjectScopeHolder(
    project: Project,
    val coroutineScope: CoroutineScope
) {
    companion object {
        @JvmStatic
        fun getInstance(project: Project): BenchProjectScopeHolder = project.service<BenchProjectScopeHolder>()
    }
}
