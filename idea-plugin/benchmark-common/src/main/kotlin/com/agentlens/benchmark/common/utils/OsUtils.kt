package com.agentlens.benchmark.common.utils


fun getOsInfo(): String {
    val name: String = System.getProperty("os.name") ?: "unknown"
    val version: String = System.getProperty("os.version") ?: "unknown"
    val arch: String = System.getProperty("os.arch") ?: "unknown"

    return "OS info: $name, version: $version, arch: $arch"
}
