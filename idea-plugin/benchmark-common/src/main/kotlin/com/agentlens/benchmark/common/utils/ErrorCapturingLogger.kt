package com.agentlens.benchmark.common.utils

import org.slf4j.event.Level
import org.slf4j.spi.LoggingEventBuilder

class ErrorCapturingLogger(private val delegate: mu.KLogger) : mu.KLogger by delegate {
    private val capturedErrors = mutableListOf<String>()

    fun getCapturedErrors(): List<String> = capturedErrors.toList()

    fun clearCapturedErrors() = capturedErrors.clear()

    override fun error(msg: () -> Any?) {
        val message = msg()?.toString() ?: ""
        capturedErrors.add(message)
        delegate.error(msg)
    }

    override fun error(t: Throwable?, msg: () -> Any?) {
        val message = msg()?.toString() ?: ""
        val fullMessage = if (t != null) {
            "$message | Exception: ${t::class.simpleName}: ${t.message}\n${t.stackTraceToString()}"
        } else {
            message
        }
        capturedErrors.add(fullMessage)
        delegate.error(t, msg)
    }

    override fun makeLoggingEventBuilder(level: Level?): LoggingEventBuilder? {
        return delegate.makeLoggingEventBuilder(level)
    }

    override fun atLevel(level: Level?): LoggingEventBuilder? {
        return delegate.atLevel(level)
    }

    override fun isEnabledForLevel(level: Level?): Boolean {
        return delegate.isEnabledForLevel(level)
    }

    override fun atTrace(): LoggingEventBuilder? {
        return delegate.atTrace()
    }

    override fun atDebug(): LoggingEventBuilder? {
        return delegate.atDebug()
    }

    override fun atInfo(): LoggingEventBuilder? {
        return delegate.atInfo()
    }

    override fun atWarn(): LoggingEventBuilder? {
        return delegate.atWarn()
    }

    override fun atError(): LoggingEventBuilder? {
        return delegate.atError()
    }
}
