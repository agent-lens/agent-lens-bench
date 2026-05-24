package com.agentlens.benchmark.runner.agent

import com.agentlens.benchmark.common.runner.agent.BenchmarkSerializationService
import com.agentlens.benchmark.common.runner.agent.BenchmarkSerializationService.Companion.polymorphic
import com.agentlens.benchmark.common.runner.agent.engine.AgentEngine
import com.agentlens.benchmark.runner.agent.engine.XDefaultAgentEngine
import kotlinx.serialization.modules.SerializersModuleBuilder

class XAgentSerializationService: BenchmarkSerializationService {
    override fun customExtensionBuilder(builder: SerializersModuleBuilder) {
        builder.apply {
            polymorphic(AgentEngine::class, XDefaultAgentEngine::class)
        }
    }
}
