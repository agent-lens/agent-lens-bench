package com.anonymous.benchmark.python.runner.agent

import com.intellij.ide.AppLifecycleListener

private val logger = mu.KotlinLogging.logger {}

class PythonAgentBenchHeadlessStartupActivity : AppLifecycleListener {
    @Suppress("UnstableApiUsage")
    override fun appStarted() {
        if (System.getProperty("agent.bench.run", "false").toBoolean()) {
            logger.info { "Running Python agent benchmark in headless mode..." }
            PythonAgentBenchmarkRunner.getInstance().runForAllProjects()
        }
    }
}
