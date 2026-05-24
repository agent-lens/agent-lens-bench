package com.agentlens.benchmark.python.runner.agent

import com.agentlens.benchmark.common.runner.agent.BenchmarkSerializationService
import com.agentlens.benchmark.common.runner.agent.BenchmarkSerializationService.Companion.polymorphic
import com.agentlens.benchmark.common.runner.agent.verifiers.Verifier
import com.agentlens.benchmark.python.runner.agent.verifiers.PythonFileRegExpCountVerifier
import com.agentlens.benchmark.python.runner.agent.verifiers.PythonRunTestVerifier
import kotlinx.serialization.modules.SerializersModuleBuilder

class PycharmSpecificBenchmarkSerializationService : BenchmarkSerializationService {
    override fun customExtensionBuilder(builder: SerializersModuleBuilder) {
        builder.apply {
            polymorphic(Verifier::class, PythonFileRegExpCountVerifier::class)
            polymorphic(Verifier::class, PythonRunTestVerifier::class)
        }
    }
}
