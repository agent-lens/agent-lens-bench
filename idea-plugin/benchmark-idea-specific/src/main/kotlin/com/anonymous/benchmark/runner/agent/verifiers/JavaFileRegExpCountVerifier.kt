package com.anonymous.benchmark.runner.agent.verifiers

import com.anonymous.benchmark.common.runner.agent.verifiers.AbstractFileRegExpCountVerifier
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
@SerialName("JavaFileRegExpCountVerifier")
@Suppress("PROVIDED_RUNTIME_TOO_LOW")
data class JavaFileRegExpCountVerifier(
    override val regExpPattern: String,
    override val searchIn: String,
    override val strictCount: Boolean,
    override val numExpected: Int = 1,
    override val uncommentedOnly: Boolean = false,
) : AbstractFileRegExpCountVerifier() {
     override fun removeCommented(fileText: String): String {
        val withoutBlockComments = Regex("/\\*.*?\\*/", setOf(RegexOption.DOT_MATCHES_ALL)).replace(fileText, "")
        return Regex("//.*").replace(withoutBlockComments, "")
    }

    override val ignoredExtensions: List<String> = listOf("class")
}
