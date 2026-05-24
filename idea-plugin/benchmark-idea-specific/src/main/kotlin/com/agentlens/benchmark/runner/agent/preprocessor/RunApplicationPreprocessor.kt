package com.agentlens.benchmark.runner.agent.preprocessor

import com.agentlens.benchmark.common.runner.agent.preprocessor.ScenarioPreprocessor
import com.intellij.execution.ProgramRunnerUtil
import com.intellij.execution.RunManager
import com.intellij.execution.application.ApplicationConfiguration
import com.intellij.execution.application.ApplicationConfigurationType
import com.intellij.execution.configurations.ConfigurationTypeUtil
import com.intellij.execution.executors.DefaultRunExecutor
import com.intellij.openapi.application.runReadAction
import com.intellij.openapi.project.Project
import com.intellij.psi.JavaPsiFacade
import com.intellij.psi.search.GlobalSearchScope
import git4idea.repo.GitRepository
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
@SerialName("RunApplicationPreprocessor")
@Suppress("PROVIDED_RUNTIME_TOO_LOW")
data class RunApplicationPreprocessor(val classFullyQualifiedName: String): ScenarioPreprocessor {
    override suspend fun prepareProject(project: Project, repo: GitRepository) {
        runReadAction {
            JavaPsiFacade.getInstance(project)
                .findClass(classFullyQualifiedName, GlobalSearchScope.projectScope(project))
                ?: error("Failed to find class '$classFullyQualifiedName'")
        }

        val runManager = RunManager.getInstance(project)

        val existing = runManager.allSettings.firstOrNull { settings ->
            val cfg = settings.configuration
            cfg is ApplicationConfiguration && cfg.mainClassName == classFullyQualifiedName
        }

        val settings = existing ?: runManager.createConfiguration(
            classFullyQualifiedName,
            ConfigurationTypeUtil.findConfigurationType(ApplicationConfigurationType::class.java)
                .configurationFactories[0]
        ).also { created ->
            val appCfg = created.configuration as ApplicationConfiguration
            appCfg.mainClassName = classFullyQualifiedName
            appCfg.setModule(appCfg.configurationModule.module)
            runManager.addConfiguration(created)
        }

        runManager.selectedConfiguration = settings

        ProgramRunnerUtil.executeConfiguration(
            settings,
            DefaultRunExecutor.getRunExecutorInstance()
        )
    }
}
