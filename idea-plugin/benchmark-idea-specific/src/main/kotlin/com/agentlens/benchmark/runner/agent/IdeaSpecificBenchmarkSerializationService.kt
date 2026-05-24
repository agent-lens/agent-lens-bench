package com.agentlens.benchmark.runner.agent

import com.agentlens.benchmark.common.runner.agent.BenchmarkSerializationService
import com.agentlens.benchmark.common.runner.agent.BenchmarkSerializationService.Companion.polymorphic
import com.agentlens.benchmark.common.runner.agent.preprocessor.ScenarioPreprocessor
import com.agentlens.benchmark.common.runner.agent.verifiers.Verifier
import com.agentlens.benchmark.runner.agent.preprocessor.RemoveTestClassPreprocessor
import com.agentlens.benchmark.runner.agent.preprocessor.RunApplicationPreprocessor
import com.agentlens.benchmark.runner.agent.preprocessor.RunBuildSystemTaskPreprocessor
import com.agentlens.benchmark.runner.agent.verifiers.JavaFileRegExpCountVerifier
import com.agentlens.benchmark.runner.agent.verifiers.JavaRunTestsVerifier
import com.agentlens.benchmark.runner.agent.verifiers.RunBuildSystemTaskVerifier
import kotlinx.serialization.modules.SerializersModuleBuilder

class IdeaSpecificBenchmarkSerializationService: BenchmarkSerializationService {
    override fun customExtensionBuilder(builder: SerializersModuleBuilder) {
        builder.apply {
            polymorphic(Verifier::class, JavaFileRegExpCountVerifier::class)
            polymorphic(Verifier::class, RunBuildSystemTaskVerifier::class)
            polymorphic(Verifier::class, JavaRunTestsVerifier::class)

            polymorphic(ScenarioPreprocessor::class, RemoveTestClassPreprocessor::class)
            polymorphic(ScenarioPreprocessor::class, RunApplicationPreprocessor::class)
            polymorphic(ScenarioPreprocessor::class, RunBuildSystemTaskPreprocessor::class)
        }
    }
}
