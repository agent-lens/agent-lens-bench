package com.anonymous.benchmark.runner.agent

import com.anonymous.benchmark.common.runner.agent.AbstractAgentBenchmarkRunner
import com.intellij.openapi.components.Service
import com.intellij.openapi.components.service
import kotlinx.coroutines.CoroutineScope

@Service(Service.Level.APP)
class JavaAgentBenchmarkRunner(scope: CoroutineScope): AbstractAgentBenchmarkRunner(scope) {
    companion object {
        fun getInstance(): JavaAgentBenchmarkRunner = service()
    }
}
