package com.anonymous.benchmark.common.runner.agent

class AgentTurnUsageInfo {
    var time: Long = 0

    var price: Double = 0.0

    val inputTokens: MutableList<Long> = mutableListOf()
    val generationTokens: MutableList<Long> = mutableListOf()
    val promptCacheHitTokens: MutableList<Long?> = mutableListOf()

    var toolCallsNumber: Int = 0
}
