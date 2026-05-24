package com.anonymous.benchmark.utils.buildSystem

import com.anonymous.benchmark.common.bundle.BenchmarkBundle
import com.anonymous.benchmark.common.utils.Either
import com.anonymous.benchmark.common.utils.Left
import com.anonymous.benchmark.common.utils.buildSystem.IdeBuildSystem
import com.intellij.execution.ConfigurationWithCommandLineShortener
import com.intellij.execution.ExecutionManager
import com.intellij.execution.Executor
import com.intellij.execution.RunManager
import com.intellij.execution.RunnerAndConfigurationSettings
import com.intellij.execution.ShortenCommandLine
import com.intellij.execution.configurations.runConfigurationType
import com.intellij.execution.executors.DefaultRunExecutor
import com.intellij.execution.runners.ExecutionEnvironment
import com.intellij.execution.runners.ExecutionUtil
import com.intellij.openapi.application.EDT
import com.intellij.openapi.application.smartReadActionBlocking
import com.intellij.openapi.application.writeIntentReadAction
import com.intellij.openapi.externalSystem.ExternalSystemModulePropertyManager
import com.intellij.openapi.externalSystem.autoimport.ExternalSystemProjectNotificationAware
import com.intellij.openapi.externalSystem.model.ProjectSystemId
import com.intellij.openapi.externalSystem.service.execution.ExternalSystemRunConfiguration
import com.intellij.openapi.externalSystem.util.ExternalSystemApiUtil
import com.intellij.openapi.externalSystem.util.ExternalSystemUtil
import com.intellij.openapi.project.Project
import com.intellij.openapi.project.modules
import com.intellij.openapi.util.Disposer
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.future.await
import kotlinx.coroutines.withContext
import mu.KotlinLogging
import org.jetbrains.idea.maven.buildtool.MavenSyncSpec
import org.jetbrains.idea.maven.execution.MavenRunConfiguration
import org.jetbrains.idea.maven.execution.MavenRunConfigurationType
import org.jetbrains.idea.maven.project.MavenProjectsManager
import org.jetbrains.kotlin.idea.configuration.GRADLE_SYSTEM_ID
import org.jetbrains.plugins.gradle.service.execution.GradleExternalTaskConfigurationType
import org.jetbrains.plugins.gradle.service.execution.GradleRunConfiguration

private val logger = KotlinLogging.logger {}

private val MAVEN_SYSTEM_ID = ProjectSystemId("Maven")

class IdeaBuildSystem: IdeBuildSystem {
    override suspend fun isRefreshRequired(project: Project): Boolean = ExternalSystemProjectNotificationAware.getInstance(project).isNotificationVisible()

    override suspend fun refresh(project: Project) {
        val systemIds = smartReadActionBlocking(project) {
            project.modules
                .mapNotNull { ExternalSystemModulePropertyManager.getInstance(it).getExternalSystemId() }
                .mapNotNull { ProjectSystemId.findById(it) }
                .toSet()
        }

        for (systemId in systemIds) {
            when (systemId) {
                GRADLE_SYSTEM_ID -> {
                    val projectPaths = smartReadActionBlocking(project) {
                        ExternalSystemApiUtil
                            .getManager(systemId)
                            ?.settingsProvider
                            ?.`fun`(project)
                            ?.linkedProjectsSettings
                            ?.mapNotNull { it.externalProjectPath }
                            ?: emptyList()
                    }

                    withContext(Dispatchers.EDT) {
                        projectPaths.forEach {
                            ExternalSystemUtil
                                .requestImport(project, it, systemId)
                                .await()
                        }
                    }
                }

                MAVEN_SYSTEM_ID -> {
                    val mavenProjectsManager = MavenProjectsManager.getInstance(project)
                    val files = smartReadActionBlocking(project) {
                        project.modules
                            .mapNotNull { mavenProjectsManager.findProject(it) }
                            .distinct()
                            .map { it.file }
                    }

                    withContext(Dispatchers.IO) {
                        mavenProjectsManager.updateMavenProjects(
                            spec = MavenSyncSpec.full("MavenProjectsManagerEx.doForceUpdateProjects"),
                            filesToUpdate = files,
                            filesToDelete = emptyList(),
                        )
                    }
                }

                else -> {
                    logger.warn { "Unsupported build system $systemId" }
                }
            }
        }
    }

    override suspend fun executeTasks(
        project: Project,
        buildSystemName: String,
        workingDirectory: String,
        tasks: List<String>
    ): Either<Throwable, String> {
        val settings = when (buildSystemName) {
            GRADLE_NAME -> {
                val runManager = RunManager.getInstance(project)
                val type = runConfigurationType<GradleExternalTaskConfigurationType>()
                runManager.createConfiguration(
                    BenchmarkBundle.message("run.configuration.configuration.name"),
                    type.factory
                )
                    .apply {
                        (configuration as GradleRunConfiguration).apply {
                            rawCommandLine = tasks.joinToString(" ")
                            settings.externalProjectPath = workingDirectory
                        }
                    }
            }

            MAVEN_NAME -> {
                val runManager = RunManager.getInstance(project)
                val type = runConfigurationType<MavenRunConfigurationType>()
                val factory = type.configurationFactories.single()
                runManager.createConfiguration(
                    BenchmarkBundle.message("run.configuration.configuration.name"),
                    factory
                )
                    .apply {
                        (configuration as MavenRunConfiguration).runnerParameters.apply {
                            goals = tasks
                            workingDirPath = workingDirectory
                        }
                    }
            }
            else -> null
        }

        if (settings == null) {
            return Left(Throwable("Unsupported build system $buildSystemName", null))
        }

        settings.isTemporary = true
        val configuration = settings.configuration
        if (configuration is ConfigurationWithCommandLineShortener) {
            configuration.shortenCommandLine = ShortenCommandLine.MANIFEST
        }

        return runConfiguration(project, settings, DefaultRunExecutor.getRunExecutorInstance())
            .waitForProcessResult()
    }

    companion object {
        private const val GRADLE_NAME = "gradle"
        private const val MAVEN_NAME = "maven"
    }
}

private suspend fun runConfiguration(
    project: Project,
    settings: RunnerAndConfigurationSettings,
    executor: Executor
): CommonProcessExecutionHandler {
    lateinit var myEnv: ExecutionEnvironment

    writeIntentReadAction {
        ExecutionUtil.doRunConfiguration(settings, executor, null, null, null) {
            myEnv = it
        }
    }

    val processExecutionHandler = CommonProcessExecutionHandler {}
    val connection = project.messageBus.connect()
    processExecutionHandler.processLifetime.onTermination {
        Disposer.dispose(connection)
    }

    val executionListener = if (settings.configuration is ExternalSystemRunConfiguration) {
        ExternalSystemExecutionListener(myEnv, processExecutionHandler)
    } else {
        DefaultExecutionListener(myEnv, processExecutionHandler)
    }

    connection.subscribe(ExecutionManager.EXECUTION_TOPIC, executionListener)
    return processExecutionHandler
}
