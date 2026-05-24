package com.agentlens.benchmark.common.utils

import kotlinx.coroutines.CancellationException
import mu.KLogger

inline fun <T> KLogger.catchExceptions(message: String = "Exception occurred", block: () -> T): Result<T> {
    return runCatching {
        block()
    }.onFailure { e ->
        if (e is CancellationException) {
            throw e
        }
        warn(e) { message }
    }
}
