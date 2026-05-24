package com.anonymous.benchmark.common.utils

import com.anonymous.benchmark.common.runner.agent.logger
import java.security.MessageDigest
import kotlin.math.max

// Indent management util for multiline string interpolation
fun String.trimAndPrependInnerBlock(
    additionalIndentation: Int = 0,
    indent: String = " ".repeat(400) + "|"
): String =
    this.trimIndent().prependIndent(" ".repeat(4 * additionalIndentation)).prependIndent(indent)

@OptIn(ExperimentalStdlibApi::class)
fun String.getSha256Hash(): String {
    val configHash = MessageDigest.getInstance("SHA-256")
        .digest(toByteArray())
        .toHexString()
    return configHash
}

fun String.normalizeLineEndings(): String = replace("\r\n", "\n")

fun String.truncateBuildOutput(lastNSymbols: Int = 2500): String {
    if (!logger.isInfoEnabled()) {
        return this
    }

    val startIndex = max(0, this.length - lastNSymbols)
    return "(Showing only the final $lastNSymbols characters. To see the complete output, set the log level to \"debug\")\n" + this.substring(startIndex)
}
