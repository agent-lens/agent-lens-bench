package com.anonymous.benchmark.common.schema

import com.anonymous.benchmark.common.runner.agent.preprocessor.ScenarioPreprocessor
import com.anonymous.benchmark.common.runner.agent.verifiers.Verifier
import com.anonymous.benchmark.common.runner.getBenchJson
import com.anonymous.benchmark.common.utils.getResourceText
import kotlinx.serialization.ExperimentalSerializationApi
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlin.io.path.Path
import kotlin.io.path.pathString

private const val CONFIG_NAME = "config.json"
private const val USER_INSTRUCTION_NAME = "user_instruction.txt"
private const val FST_USER_MESSAGE_NAME = "first_user_message.md"

@Serializable
@Suppress("PROVIDED_RUNTIME_TOO_LOW")
data class AgentScenario(
    val verifiers: List<Verifier>,
    val projectPath: String,
    val openedFiles: List<String>,
    val userInstruction: String = "",
    val firstUserMessage: String = "",
    val fixedFstUserMessage: Boolean = false,
    val language: ScenarioLanguage = ScenarioLanguage.English,
    val scenarioPath: String = "",
    val repoHash: String? = null,
    val branch: String? = null,
    val maxSteps: Int = 10,
    val tags: List<String> = emptyList(),
    val preprocessors: List<ScenarioPreprocessor> = emptyList(),
    val mcpServers: List<BenchHttpMcpServerConfiguration> = emptyList(),
    val scenarioTimeoutSeconds: Long = 20 * 60,
    val agentTurnTimeoutSeconds: Long = 15 * 60,
    val verifierTimeoutSeconds: Long = 5 * 60,
) {
    fun getAgentSettings(): AgentScenarioSettings {
        return AgentScenarioSettings(
            language,
            mcpServers
        )
    }

    companion object {
        @OptIn(ExperimentalSerializationApi::class)
        fun buildScenarioFromPath(scenarioPath: String): AgentScenario {
            val configPath = Path(scenarioPath, CONFIG_NAME).pathString
            val configText = getResourceText(configPath)
                ?: error("Could not find '$CONFIG_NAME' under scenario path '$scenarioPath'")

            val userInstructionPath = Path(scenarioPath, USER_INSTRUCTION_NAME).pathString
            val userInstruction = getResourceText(userInstructionPath)?.trim()
                ?: error("Could not find '$USER_INSTRUCTION_NAME' under scenario path '$scenarioPath'")

            return getBenchJson().decodeFromString<AgentScenario>(configText).let { config ->
                var fstUserMessage = ""
                if (config.fixedFstUserMessage) {
                    val fstUserMessagePath = Path(scenarioPath, FST_USER_MESSAGE_NAME).pathString
                    fstUserMessage = getResourceText(fstUserMessagePath)?.trim()
                        ?: error("Could not find '$FST_USER_MESSAGE_NAME' under scenario path '$scenarioPath'")
                }


                config.copy(
                    userInstruction = userInstruction,
                    firstUserMessage = fstUserMessage,
                    scenarioPath = scenarioPath,
                    mcpServers = config.mcpServers.map { server ->
                        server.copy(
                            headers = server.headers.mapValues { (_, value) ->
                                val token = Regex("\\$.*\\$").find(value)?.value
                                if (token == null) {
                                    value
                                } else {
                                    val tokenEnvValue = System.getenv(token.drop(1).dropLast(1)) ?:
                                        error("Please set token value for MCP server as environment variable: '$token'")
                                    value.replace(token, tokenEnvValue)
                                }
                            }
                        )
                    }
                )
            }
        }
    }
}

enum class ScenarioLanguage {
    @SerialName("English")
    English,

    @SerialName("Russian")
    Russian,

    @SerialName("Chinese")
    Chinese,
}

data class AgentScenarioSettings(
    val scenarioLanguage: ScenarioLanguage,
    val mcpServers: List<BenchHttpMcpServerConfiguration> = emptyList(),
)
