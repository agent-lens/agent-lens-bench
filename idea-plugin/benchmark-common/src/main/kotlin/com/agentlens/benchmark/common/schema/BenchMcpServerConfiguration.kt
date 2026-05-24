@file:Suppress("PROVIDED_RUNTIME_TOO_LOW")
package com.agentlens.benchmark.common.schema

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable


@Serializable
sealed class BenchMcpServerConfiguration {
    abstract val name: String
    abstract fun getTransportType(): String

    companion object {
        const val STDIO = "stdio"
        const val HTTP = "http"
        const val SSE = "sse"
    }
}

@Serializable
@SerialName(BenchMcpServerConfiguration.STDIO)
data class BenchStdioMcpServerConfiguration(
    override val name: String,
    val command: String,
    val args: List<String> = emptyList(),
    val env: Map<String, String> = emptyMap(),
) : BenchMcpServerConfiguration() {
    override fun getTransportType(): String = STDIO
}

@Serializable
@SerialName(BenchMcpServerConfiguration.HTTP)
data class BenchHttpMcpServerConfiguration(
    override val name: String,
    val url: String,
    val headers: Map<String, String> = emptyMap(),
) : BenchMcpServerConfiguration() {
    override fun getTransportType(): String = HTTP
}

@Serializable
@SerialName(BenchMcpServerConfiguration.SSE)
data class BenchSseMcpServerConfiguration(
    override val name: String,
    val url: String,
    val headers: Map<String, String> = emptyMap(),
) : BenchMcpServerConfiguration() {
    override fun getTransportType(): String = SSE
}


