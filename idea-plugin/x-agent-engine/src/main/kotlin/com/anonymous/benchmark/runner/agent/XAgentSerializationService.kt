package com.anonymous.benchmark.runner.agent

import com.anonymous.benchmark.common.runner.agent.BenchmarkSerializationService
import com.anonymous.benchmark.common.runner.agent.BenchmarkSerializationService.Companion.polymorphic
import com.anonymous.benchmark.common.runner.agent.engine.AgentEngine
import com.anonymous.benchmark.runner.agent.engine.XDefaultAgentEngine
import kotlinx.serialization.modules.SerializersModuleBuilder

class XAgentSerializationService: BenchmarkSerializationService {
    override fun customExtensionBuilder(builder: SerializersModuleBuilder) {
        builder.apply {
            polymorphic(AgentEngine::class, XDefaultAgentEngine::class)
        }
    }
}
