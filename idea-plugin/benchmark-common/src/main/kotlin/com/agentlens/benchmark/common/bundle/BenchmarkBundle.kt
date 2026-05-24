package com.agentlens.benchmark.common.bundle

import com.intellij.DynamicBundle
import org.jetbrains.annotations.PropertyKey

private const val BUNDLE = "messages.BenchmarkTexts"

object BenchmarkBundle {
    private val bundle = DynamicBundle(this::class.java, BUNDLE)

    @JvmStatic
    fun message(@PropertyKey(resourceBundle = BUNDLE) key: String, vararg params: Any): String =
        bundle.getMessage(key, *params)
}
