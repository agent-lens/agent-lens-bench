package com.anonymous.benchmark.runner.agent

import com.anonymous.benchmark.common.runner.agent.BenchmarkSerializationService
import com.anonymous.benchmark.common.runner.agent.BenchmarkSerializationService.Companion.polymorphic
import com.anonymous.benchmark.common.runner.agent.preprocessor.ScenarioPreprocessor
import com.anonymous.benchmark.common.runner.agent.verifiers.Verifier
import com.anonymous.benchmark.runner.agent.preprocessor.RemoveTestClassPreprocessor
import com.anonymous.benchmark.runner.agent.preprocessor.RunApplicationPreprocessor
import com.anonymous.benchmark.runner.agent.preprocessor.RunBuildSystemTaskPreprocessor
import com.anonymous.benchmark.runner.agent.verifiers.JavaFileRegExpCountVerifier
import com.anonymous.benchmark.runner.agent.verifiers.JavaRunTestsVerifier
import com.anonymous.benchmark.runner.agent.verifiers.RunBuildSystemTaskVerifier
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
