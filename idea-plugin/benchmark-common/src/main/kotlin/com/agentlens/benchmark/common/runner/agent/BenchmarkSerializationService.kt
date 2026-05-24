package com.agentlens.benchmark.common.runner.agent

import com.agentlens.benchmark.common.runner.agent.engine.AgentEngine
import com.agentlens.benchmark.common.runner.agent.engine.ExternalAgentEngine
import com.agentlens.benchmark.common.runner.agent.verifiers.ChatOrToolRegExpCountVerifier
import com.agentlens.benchmark.common.runner.agent.verifiers.ChatRegExpCountVerifier
import com.agentlens.benchmark.common.runner.agent.verifiers.ExactFileMatchVerifier
import com.agentlens.benchmark.common.runner.agent.verifiers.NewFileRegExpVerifier
import com.agentlens.benchmark.common.runner.agent.verifiers.NoChangesVerifier
import com.agentlens.benchmark.common.runner.agent.verifiers.NoFileErrorsVerifier
import com.agentlens.benchmark.common.runner.agent.verifiers.Verifier
import com.agentlens.benchmark.common.runner.agent.verifiers.YesChangesVerifier
import com.intellij.openapi.extensions.ExtensionPointName
import kotlinx.serialization.ExperimentalSerializationApi
import kotlinx.serialization.InternalSerializationApi
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonNamingStrategy
import kotlinx.serialization.modules.SerializersModule
import kotlinx.serialization.modules.SerializersModuleBuilder
import kotlinx.serialization.serializer
import kotlin.reflect.KClass

interface BenchmarkSerializationService {
    fun customExtensionBuilder(builder: SerializersModuleBuilder)

    companion object {
        private val EP_NAME =
            ExtensionPointName<BenchmarkSerializationService>("com.agentlens.benchmark.serializationService")

        private fun getBenchJson(extensions: List<BenchmarkSerializationService>): Json {
            val module = SerializersModule {
                polymorphic(AgentEngine::class, ExternalAgentEngine::class)

                polymorphic(Verifier::class, NoChangesVerifier::class)
                polymorphic(Verifier::class, YesChangesVerifier::class)
                polymorphic(Verifier::class, NoFileErrorsVerifier::class)
                polymorphic(Verifier::class, ChatRegExpCountVerifier::class)
                polymorphic(Verifier::class, ChatOrToolRegExpCountVerifier::class)
                polymorphic(Verifier::class, ExactFileMatchVerifier::class)
                polymorphic(Verifier::class, NewFileRegExpVerifier::class)

                for (extension in extensions) {
                    extension.customExtensionBuilder(this)
                }
            }


            @OptIn(ExperimentalSerializationApi::class)
            return Json {
                prettyPrint = true
                namingStrategy = JsonNamingStrategy.SnakeCase
                serializersModule = module
                ignoreUnknownKeys = true
            }
        }

        @OptIn(InternalSerializationApi::class)
        fun <Base : Any, Sub : Base> SerializersModuleBuilder.polymorphic(base: KClass<Base>, sub: KClass<Sub>) {
            polymorphic(base, sub, sub.serializer())
        }

        fun getBenchJson(): Json  {
            return getBenchJson(EP_NAME.extensionList)
        }
    }
}
