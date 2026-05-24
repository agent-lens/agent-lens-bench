package com.anonymous.benchmark.utils.buildSystem

import com.intellij.execution.process.ProcessHandler
import com.intellij.execution.runners.ExecutionEnvironment
import com.intellij.openapi.externalSystem.service.execution.ExternalSystemProcessHandler
import com.intellij.openapi.externalSystem.service.notification.ExternalSystemProgressNotificationManager

private val logger = mu.KotlinLogging.logger {}

class ExternalSystemExecutionListener(
    myEnv: ExecutionEnvironment,
    processExecutionHandler: CommonProcessExecutionHandler
) : AbstractExecutionListener(myEnv, processExecutionHandler) {
    override fun processStarting(executorId: String, env: ExecutionEnvironment, handler: ProcessHandler) {
        if (env != myEnv) return

        val myExternalSystemTaskId = (handler as? ExternalSystemProcessHandler)?.task?.id

        if (myExternalSystemTaskId == null) {
            logger.warn(Exception()) {
                "Run configuration process is starting, but cannot extract external system task id, terminal listener was not attached"
            }
            processExecutionHandler.finishOutputCollecting()
        } else {
            ExternalSystemProgressNotificationManager.getInstance()
                .addNotificationListener(
                    myExternalSystemTaskId,
                    ExternalSystemTerminalOutputListener(processExecutionHandler)
                )
        }
    }
}

