package com.agentlens.benchmark.common.runner.agent.verifiers

import com.agentlens.benchmark.common.schema.Message
import com.agentlens.benchmark.common.utils.Either
import com.agentlens.benchmark.common.utils.map
import com.agentlens.benchmark.common.utils.recover
import com.intellij.openapi.project.Project
import kotlinx.serialization.Serializable

@Serializable
@Suppress("PROVIDED_RUNTIME_TOO_LOW")
abstract class AbstractTestRegExpCountVerifier : Verifier {

    abstract val regExpPattern: String
    abstract val path: String
    abstract val strictCount: Boolean
    abstract val numExpected: Int
    abstract val includeSubdirs: Boolean

    abstract suspend fun getTestsOutput(project: Project): Either<String, String>

    override suspend fun verify(
        project: Project,
        scenarioPath: String,
        chatHistory: List<Message>
    ): VerifierResult {
        val regExp = Regex(regExpPattern)

        val count = getTestsOutput(project).map { regExp.findAll(it).count() }.recover {
            return VerifierResult.Failure(it)
        }

        return if (count == numExpected || (!strictCount && count >= numExpected)) {
            VerifierResult.Success
        } else {
            VerifierResult.Failure(
                "Expected ${if (strictCount) "exactly" else "at least"} $numExpected matches of '$regExpPattern' " +
                        "in test outputs at '$path', but got $count"
            )
        }
    }
}
