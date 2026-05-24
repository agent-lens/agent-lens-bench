package com.anonymous.benchmark.runner.agent

import com.intellij.ide.AppLifecycleListener
import mu.KotlinLogging

private val logger = KotlinLogging.logger {}

class JavaAgentBenchHeadlessStartupActivity : AppLifecycleListener {

    @Suppress("UnstableApiUsage")
    override fun appStarted() {
        logger.info("Starting application...")
        if (System.getProperty("agent.bench.run", "false").toBoolean()) {
            logger.info { "Running Java agent benchmark in headless mode..." }
            JavaAgentBenchmarkRunner.getInstance().runForAllProjects()
        }
    }
}
