package com.anonymous.benchmark.utils.buildSystem

import com.intellij.execution.process.ProcessAdapter
import com.intellij.execution.process.ProcessEvent
import com.intellij.execution.process.ProcessHandler
import com.intellij.execution.process.ProcessOutputType
import com.intellij.execution.runners.ExecutionEnvironment
import com.intellij.execution.testframework.sm.ServiceMessageUtil
import com.intellij.execution.testframework.sm.runner.OutputEventSplitter
import com.intellij.openapi.util.Key
import jetbrains.buildServer.messages.serviceMessages.TestFailed
import jetbrains.buildServer.messages.serviceMessages.TestStdErr
import jetbrains.buildServer.messages.serviceMessages.TestStdOut
import mu.KotlinLogging
import java.text.ParseException

private val logger = KotlinLogging.logger { }

class DefaultExecutionListener(
    myEnv: ExecutionEnvironment,
    processExecutionHandler: CommonProcessExecutionHandler
) : AbstractExecutionListener(myEnv, processExecutionHandler) {

    override fun processStarting(executorId: String, env: ExecutionEnvironment, handler: ProcessHandler) {
        if (env != myEnv) return

        val eventSplitter = object : OutputEventSplitter() {
            override fun onTextAvailable(text: String, outputType: Key<*>) {
                val parsedMessage = try {
                    ServiceMessageUtil.parse(text.trim(), false)
                } catch (e: ParseException) {
                    logger.warn(e) { "Can not parse text: $text, using as is" }
                    null
                }
                if (parsedMessage != null) {
                    when (parsedMessage) {
                        is TestStdOut -> addToBuffer("\n${parsedMessage.stdOut}", outputType)
                        is TestStdErr -> addToBuffer("\n${parsedMessage.stdErr}", outputType)
                        is TestFailed -> {
                            addToBuffer("\n${parsedMessage.failureMessage}", outputType)
                            addToBuffer("\n${parsedMessage.stacktrace}", outputType)
                        }
                    }
                } else {
                    addToBuffer(text, outputType)
                }
            }

            private fun addToBuffer(text: String, outputType: Key<*>) {
                if (ProcessOutputType.isStdout(outputType)) {
                    processExecutionHandler.addStdout(text)
                } else if (ProcessOutputType.isStderr(outputType)) {
                    processExecutionHandler.addStderr(text)
                }
            }
        }

        handler.addProcessListener(object : ProcessAdapter() {
            override fun onTextAvailable(event: ProcessEvent, outputType: Key<*>) {
                eventSplitter.process(event.text, outputType)
            }

            override fun processNotStarted() {
                processExecutionHandler.finishOutputCollecting()
            }

            override fun processTerminated(event: ProcessEvent) {
                processExecutionHandler.finishOutputCollecting()
            }
        })

        logger.info { "Run configuration process is starting according to Intellij" }
    }
}
