package com.anonymous.benchmark.utils.buildSystem

import com.intellij.build.events.OutputBuildEvent
import com.intellij.openapi.externalSystem.model.task.ExternalSystemTaskId
import com.intellij.openapi.externalSystem.model.task.ExternalSystemTaskNotificationEvent
import com.intellij.openapi.externalSystem.model.task.ExternalSystemTaskNotificationListener
import com.intellij.openapi.externalSystem.model.task.event.ExternalSystemTaskExecutionEvent
import com.intellij.openapi.externalSystem.service.notification.ExternalSystemProgressNotificationManager
import com.intellij.openapi.externalSystem.util.ExternalSystemUtil

class ExternalSystemTerminalOutputListener(
    private val processExecutionHandler: CommonProcessExecutionHandler
) : ExternalSystemTaskNotificationListener {
    override fun onTaskOutput(id: ExternalSystemTaskId, text: String, stdOut: Boolean) {
        if (stdOut) {
            processExecutionHandler.addStdout(text)
        } else {
            processExecutionHandler.addStderr(text)
        }
    }

    override fun onStatusChange(event: ExternalSystemTaskNotificationEvent) {
        if (event is ExternalSystemTaskExecutionEvent) {
            val buildEvent = ExternalSystemUtil.convert(event)
            if (buildEvent is OutputBuildEvent) {
                if (buildEvent.isStdOut) {
                    processExecutionHandler.addStdout(buildEvent.message)
                } else {
                    processExecutionHandler.addStderr(buildEvent.message)
                }
            }
        }
    }

    override fun onEnd(projectPath: String, id: ExternalSystemTaskId) {
        onEnd(id)
    }

    override fun onEnd(id: ExternalSystemTaskId) {
        ExternalSystemProgressNotificationManager.getInstance()
            .removeNotificationListener(this)

        processExecutionHandler.finishOutputCollecting()
    }
}
