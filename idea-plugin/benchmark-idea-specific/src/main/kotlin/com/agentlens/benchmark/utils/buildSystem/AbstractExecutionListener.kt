package com.agentlens.benchmark.utils.buildSystem

import com.intellij.execution.ExecutionListener
import com.intellij.execution.process.ProcessHandler
import com.intellij.execution.runners.ExecutionEnvironment

private val logger = mu.KotlinLogging.logger {}

abstract class AbstractExecutionListener(
    protected val myEnv: ExecutionEnvironment,
    protected val processExecutionHandler: CommonProcessExecutionHandler
) : ExecutionListener {
    abstract override fun processStarting(executorId: String, env: ExecutionEnvironment, handler: ProcessHandler)

    override fun processStarted(executorId: String, env: ExecutionEnvironment, handler: ProcessHandler) {
        if (env == myEnv) {
            logger.info { "Run configuration process started according to Intellij" }
            processExecutionHandler.afterProcessStartedCallback.invoke()
        }
    }

    override fun processNotStarted(executorId: String, env: ExecutionEnvironment, cause: Throwable?) {
        if (env == myEnv) {
            logger.warn(cause) { "Run configuration process not started according to Intellij" }
            processExecutionHandler.exitCode.complete(null)
            processExecutionHandler.processLifetime.terminate()
            processExecutionHandler.reportProcessNotStarted(cause)
            processExecutionHandler.afterProcessStartedCallback.invoke()
        }
    }

    override fun processNotStarted(executorId: String, env: ExecutionEnvironment) =
        processNotStarted(executorId, env, null)

    override fun processTerminated(
        executorId: String,
        env: ExecutionEnvironment,
        handler: ProcessHandler,
        exitCode: Int
    ) {
        if (env == myEnv) {
            logger.info { "Run configuration process terminated according to Intellij with exit code $exitCode" }
            processExecutionHandler.exitCode.complete(exitCode)
            processExecutionHandler.processLifetime.terminate()
        }
    }
}
