package com.anonymous.benchmark.common.utils

import kotlinx.serialization.json.Json
import kotlinx.serialization.encodeToString as encodeToStringCompatibility

object JsonUtils {
    val json = Json {
        encodeDefaults = true
        ignoreUnknownKeys = true
    }

    val prettyJson = Json(json) {
        prettyPrint = true
    }
}

inline fun <reified T> Json.encodeToStringCompat(value: T) = encodeToStringCompatibility(value)
