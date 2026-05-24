package com.agentlens.benchmark.common.utils

import com.intellij.execution.configurations.GeneralCommandLine
import com.intellij.execution.process.OSProcessHandler
import com.intellij.execution.process.ProcessEvent
import com.intellij.execution.process.ProcessListener
import com.intellij.execution.process.ProcessOutputTypes
import com.intellij.openapi.util.Key
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.withTimeout
import kotlin.coroutines.cancellation.CancellationException

sealed interface ExecutionResult {
    data class SuccessExecutionResult(val exitCode: Int, val output: String) : ExecutionResult
    data class FailedExecutionResult(val reason: String) : ExecutionResult
}

inline fun ExecutionResult.recover(
    supplier: (ExecutionResult.FailedExecutionResult) -> ExecutionResult.SuccessExecutionResult
) =
    when (this) {
        is ExecutionResult.SuccessExecutionResult -> this
        is ExecutionResult.FailedExecutionResult -> supplier(this)
    }

class TerminalCommandExecutor {
    suspend fun execute(
        args: List<String>,
        timeoutMs: Long? = null,
        cmdSetup: GeneralCommandLine.() -> GeneralCommandLine?
    ): ExecutionResult {
        val timeoutMs = timeoutMs ?: TERMINAL_TIMEOUT_MS
        require(timeoutMs > 0) { "timeoutMs must be > 0" }

        val cmd = GeneralCommandLine(args)
            .cmdSetup()
            ?: return ExecutionResult.FailedExecutionResult("Failed to setup terminal command")

        val processHandler = OSProcessHandler(cmd)
        val output = StringBuffer()
        val exitCode = CompletableDeferred<Int>()

        processHandler.addProcessListener(object : ProcessListener {
            override fun onTextAvailable(event: ProcessEvent, outputType: Key<*>) {
                if (outputType == ProcessOutputTypes.STDOUT || outputType == ProcessOutputTypes.STDERR) {
                    val text = event.text

                    if (output.length + text.length > BUFFER_LIMIT) {
                        output.delete(0, output.length + text.length - BUFFER_LIMIT)
                    }

                    output.append(text)
                }
            }

            override fun processTerminated(event: ProcessEvent) {
                exitCode.complete(event.exitCode)
            }
        })

        processHandler.startNotify()

        try {
            val processExitCode = withTimeout(timeoutMs) { exitCode.await() }
            return ExecutionResult.SuccessExecutionResult(processExitCode, output.toString())
        } catch (exception: Throwable) {
            return when (exception) {
                is TimeoutCancellationException -> ExecutionResult.FailedExecutionResult(EXECUTION_TIMEOUT_MESSAGE)
                is CancellationException -> throw exception
                else -> ExecutionResult.FailedExecutionResult(exception.stackTraceToString())
            }
        } finally {
            processHandler.destroyProcess()
        }
    }

    companion object {
        private const val TERMINAL_TIMEOUT_MS = 300_000L
        private const val EXECUTION_TIMEOUT_MESSAGE = "Execution timed out"

        private const val BUFFER_LIMIT = 10_000_000
    }
}
