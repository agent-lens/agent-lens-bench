package com.agentlens.benchmark.common.runner.agent

import mu.KotlinLogging

private val log = KotlinLogging.logger {}


object PriceCalculator {

    /** Per-million-token costs: inputPrice / outputPrice */
    private data class ModelPricing(
        val inputPerMillion: Double,
        val cachedInputPerMillion: Double,
        val outputPerMillion: Double,
    )

    private val PRICING_TABLE: Map<String, ModelPricing> = mapOf(
        // GPT-5 family
        "gpt-5" to ModelPricing(1.25, 0.125, 10.00),
        "gpt-5-mini" to ModelPricing(0.25, 0.025, 2.00),

        // TODO add gpt-5.2, etc.
    )

    /** Fallback pricing when model is not in the table (GPT-4o rates). */
    private val DEFAULT_PRICING = ModelPricing(2.50, 1.25, 10.00)

    private const val TOKENS_PER_MILLION = 1_000_000.0

    /**
     * Calculates the dollar cost of a single LLM request.
     *
     * @param modelName        the OpenAI model name (e.g. "gpt-5")
     * @param promptTokens     total prompt tokens consumed
     * @param completionTokens total completion/generation tokens
     * @param cachedTokens     prompt tokens served from cache (subset of [promptTokens])
     */
    fun calculatePrice(
        modelName: String,
        promptTokens: Long,
        completionTokens: Long,
        cachedTokens: Long = 0,
    ): Double {
        val pricing = PRICING_TABLE[modelName]
            ?: DEFAULT_PRICING.also {
                log.warn { "No pricing entry for model '$modelName', falling back to default (GPT-4o) rates" }
            }
        val nonCachedPromptTokens = (promptTokens - cachedTokens).coerceAtLeast(0)

        val inputCost = nonCachedPromptTokens * pricing.inputPerMillion / TOKENS_PER_MILLION
        val cachedCost = cachedTokens * pricing.cachedInputPerMillion / TOKENS_PER_MILLION
        val outputCost = completionTokens * pricing.outputPerMillion / TOKENS_PER_MILLION

        return inputCost + cachedCost + outputCost
    }
}
