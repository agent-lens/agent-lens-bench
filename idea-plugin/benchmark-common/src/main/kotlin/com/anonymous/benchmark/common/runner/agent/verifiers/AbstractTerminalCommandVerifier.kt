package com.anonymous.benchmark.common.runner.agent.verifiers

import com.anonymous.benchmark.common.schema.Message
import com.anonymous.benchmark.common.utils.ExecutionResult
import com.anonymous.benchmark.common.utils.TerminalCommandExecutor
import com.intellij.execution.configurations.GeneralCommandLine
import com.intellij.openapi.project.Project

abstract class AbstractTerminalCommandVerifier : Verifier {

    abstract val timeoutMs: Long?

    abstract fun buildCommand(project: Project): List<String>
    abstract fun GeneralCommandLine.commandSetup(project: Project): GeneralCommandLine?

    abstract fun parseSuccessResult(output: String): VerifierResult

    override suspend fun verify(
        project: Project,
        scenarioPath: String,
        chatHistory: List<Message>
    ): VerifierResult {
        val command = buildCommand(project)
        val result = TerminalCommandExecutor().execute(command, timeoutMs) { commandSetup(project) }
        return when (result) {
            is ExecutionResult.SuccessExecutionResult -> {
                if (result.exitCode != 0) {
                    VerifierResult.Failure(
                        buildString {
                            appendLine(
                                "Command line execution in TestVerifier ended with exit code ${result.exitCode}."
                            )
                            append("Output: ${result.output}")
                        }
                    )
                } else {
                    parseSuccessResult(result.output)
                }
            }

            is ExecutionResult.FailedExecutionResult -> VerifierResult.Failure(result.reason)
        }
    }
}
