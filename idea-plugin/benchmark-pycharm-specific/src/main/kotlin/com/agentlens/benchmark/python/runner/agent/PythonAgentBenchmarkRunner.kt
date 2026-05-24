package com.agentlens.benchmark.python.runner.agent

import com.agentlens.benchmark.common.runner.agent.AbstractAgentBenchmarkRunner
import com.agentlens.benchmark.common.utils.getProjectDir
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.application.backgroundWriteAction
import com.intellij.openapi.components.Service
import com.intellij.openapi.components.service
import com.intellij.openapi.module.Module
import com.intellij.openapi.module.ModuleManager
import com.intellij.openapi.project.Project
import com.intellij.openapi.projectRoots.ProjectJdkTable
import com.intellij.openapi.projectRoots.Sdk
import com.intellij.openapi.roots.ProjectRootManager
import com.jetbrains.python.sdk.PythonSdkType
import com.jetbrains.python.sdk.PythonSdkUpdater
import com.jetbrains.python.sdk.PythonSdkUtil
import com.jetbrains.python.sdk.pythonSdk
import kotlinx.coroutines.CoroutineScope
import mu.KotlinLogging

private val logger = KotlinLogging.logger {}

@Service(Service.Level.APP)
@Suppress("DEPRECATION")
class PythonAgentBenchmarkRunner(scope: CoroutineScope) : AbstractAgentBenchmarkRunner(scope) {

    override suspend fun loadProject(projectPath: String): Project? {
        val project = super.loadProject(projectPath) ?: return null

        ModuleManager.getInstance(project).modules.firstOrNull()
            ?.also {
                ensurePythonSdkConfigured(project, it)
            }

        return project
    }

    private suspend fun ensurePythonSdkConfigured(project: Project, module: Module) {
        PythonSdkUtil.findPythonSdk(module)?.also {
            logger.info { "Python SDK already configured for module `${module.name}`: ${it.name}" }
            return
        }

        ProjectRootManager.getInstance(project).projectSdk?.also { projectSdk ->
            if (PythonSdkUtil.isPythonSdk(projectSdk)) {
                module.pythonSdk = projectSdk
                logger.info {
                    "Python SDK configured from project SDK: ${projectSdk.name}, ${projectSdk.versionString}"
                }
                return
            }
        }

        PythonSdkUtil.getAllSdks().firstOrNull()?.also { existingSdk ->
            module.pythonSdk = existingSdk
            logger.info {
                "Python SDK configured from existing registered SDK: " +
                        "${existingSdk.name}, ${existingSdk.versionString}"
            }
            return
        }

        logger.warn { "No existing Python SDK found; falling back to manual .venv SDK creation" }
        val manualSdk = getOrCreateVenvSdk(project)

        PythonSdkUpdater.updateVersionAndPathsSynchronouslyAndScheduleRemaining(manualSdk, project)
        module.pythonSdk = manualSdk
    }

    companion object {
        fun getInstance(): PythonAgentBenchmarkRunner = service()

        private const val VENV_PATH = ".venv/bin/python"

        private suspend fun getOrCreateVenvSdk(project: Project): Sdk {
            val projectDir = getProjectDir(project)
            val pythonPath = "$projectDir/$VENV_PATH"

            ProjectJdkTable.getInstance()
                .allJdks
                .firstOrNull { it.homePath == pythonPath }
                ?.also { return it }

            val sdk = ProjectJdkTable.getInstance().createSdk("Remote-CI-Venv", PythonSdkType.getInstance())

            val modificator = sdk.sdkModificator
            modificator.homePath = pythonPath
            modificator.versionString = "Python 3.x (CI)"

            backgroundWriteAction {
                ApplicationManager.getApplication().runWriteAction {
                    modificator.commitChanges()
                    ProjectJdkTable.getInstance().addJdk(sdk)
                }
            }

            return sdk
        }
    }
}
