package com.agentlens.benchmark.common.utils.buildSystem

import com.agentlens.benchmark.common.utils.Either
import com.agentlens.benchmark.common.utils.catchExceptions
import com.intellij.openapi.extensions.ExtensionPointName
import com.intellij.openapi.project.Project
import mu.KotlinLogging
import kotlin.collections.forEach
import kotlin.collections.ifEmpty

private val logger = KotlinLogging.logger {}

interface IdeBuildSystem {
    suspend fun isRefreshRequired(project: Project): Boolean
    suspend fun refresh(project: Project)
    suspend fun executeTasks(
        project: Project,
        buildSystemName: String,
        workingDirectory: String,
        tasks: List<String>
    ): Either<Throwable, String>

    companion object {
        private val EP_NAME =
            ExtensionPointName<IdeBuildSystem>("com.agentlens.benchmark.common.ideBuildSystem")

        fun getInstances(): List<IdeBuildSystem> = EP_NAME.extensions.toList()

        suspend fun refreshBuildSystemIfRequired(project: Project, forceRefresh: Boolean = false) {
            logger.catchExceptions {
                val buildSystems = getInstances()

                val buildSystemToRefresh = buildSystems
                    .filter { forceRefresh || it.isRefreshRequired(project) }
                    .ifEmpty { return }
                logger.info("Refreshing build system...")
                buildSystemToRefresh.forEach { it.refresh(project) }
            }
        }
    }

}
