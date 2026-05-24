package com.anonymous.benchmark.common.schema


data class LlmUsage(
    val price: Double = 0.0,
    val promptTokens: Long = 0,
    val generationTokens: Long = 0,
    val promptCacheHitTokens: Long? = null
) {
    operator fun plus(usage: LlmUsage): LlmUsage =
        LlmUsage(
            price = price + usage.price,
            promptTokens = promptTokens + usage.promptTokens,
            generationTokens = generationTokens + usage.generationTokens,
            promptCacheHitTokens = promptCacheHitTokens?.plus(usage.promptCacheHitTokens ?: 0)
            ?: usage.promptCacheHitTokens
        )
}
