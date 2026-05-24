package com.agentlens.benchmark.python.runner.agent.verifiers

import com.agentlens.benchmark.common.runner.agent.verifiers.AbstractFileRegExpCountVerifier
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
@SerialName("PythonFileRegExpCountVerifier")
@Suppress("PROVIDED_RUNTIME_TOO_LOW")
data class PythonFileRegExpCountVerifier(
    override val regExpPattern: String,
    override val searchIn: String,
    override val strictCount: Boolean,
    override val numExpected: Int = 1,
    override val uncommentedOnly: Boolean = false,
): AbstractFileRegExpCountVerifier() {
    override fun removeCommented(fileText: String): String {
        return Regex("#.*").replace(fileText, "")
    }

    override val ignoredExtensions: List<String> = listOf("")
}
