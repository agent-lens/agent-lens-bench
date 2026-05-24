package com.agentlens.benchmark.common.runner.agent

import com.intellij.openapi.application.ApplicationManager

object AgentEnvService {
    private val envVariables: Map<EnvVariable, String?> = EnvVariable.entries.associateWith { System.getenv(it.name) }

    fun validate(isHeadless: Boolean) {
        validateEnvVariable(EnvVariable.SIMULATOR_MODEL_NAME, isHeadless)
        validateEnvVariable(EnvVariable.SIMULATOR_BASE_URL, isHeadless)
        validateEnvVariable(EnvVariable.SIMULATOR_API_KEY, isHeadless)
        validateEnvVariable(EnvVariable.AGENT_API_KEY, isHeadless)
        validateEnvVariable(EnvVariable.PLUGIN_COMMIT_HASH, isHeadless)
        if (isHeadless) {
            validateEnvVariable(EnvVariable.WHERE_TO_SAVE_DUMPS, true)
            validateEnvVariable(EnvVariable.PROJECTS_ROOT_DIR, true)
            validateEnvVariable(EnvVariable.PROVIDER_NAME, true)
            // MODEL_URL and MODEL_NAME are optional, skip them
        }
    }

    fun getEnvValue(envVariable: EnvVariable): String? = envVariables[envVariable]

    private fun validateEnvVariable(envVariable: EnvVariable, shouldExit: Boolean) {
        if (envVariables[envVariable] != null) {
            return
        }

        val errorMessage = "No ${envVariable.name} provided - please set it as an environment variable"
        if (shouldExit) {
            ApplicationManager.getApplication().exit(true, true, false, 1)
        }

        error(errorMessage)
    }

}

enum class EnvVariable {
    SIMULATOR_MODEL_NAME,
    SIMULATOR_BASE_URL,
    SIMULATOR_API_KEY,
    AGENT_API_KEY,
    EXP_NAME,
    WHERE_TO_SAVE_DUMPS,
    CONFIG_FILE_PATH,
    CLEAR_FOLDER,
    USE_ALL_USERS,
    PROJECTS_ROOT_DIR,
    PLUGIN_COMMIT_HASH,

    PROVIDER_NAME,
    MODEL_NAME,
    MODEL_URL,

    AGENT_ENGINE_URL
}
