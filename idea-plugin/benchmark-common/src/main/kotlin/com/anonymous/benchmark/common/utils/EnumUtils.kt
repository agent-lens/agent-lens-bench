package com.anonymous.benchmark.common.utils

val <T : Enum<T>> T.visibleName: String
    get() {
        return name.lowercase()
    }
