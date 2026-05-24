package com.agentlens.benchmark.utils.buildSystem

import com.agentlens.benchmark.common.utils.Either
import com.agentlens.benchmark.common.utils.Left
import com.agentlens.benchmark.common.utils.Right
import com.intellij.openapi.observable.properties.AtomicProperty
import com.intellij.openapi.observable.properties.ObservableMutableProperty
import com.jetbrains.rd.util.lifetime.LifetimeDefinition
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Deferred
import kotlin.collections.plus


enum class TerminalOutputType {
    STDOUT, STDERR
}

data class TerminalOutputEvent(
    val text: String,
    val type: TerminalOutputType,
)

data class TerminalOutput(
    val chunks: List<TerminalOutputEvent>,
) {
    fun getText(type: TerminalOutputType? = null): String {
        val usefulChunks = if (type == null) {
            chunks
        } else {
            chunks.filter { it.type == type }
        }
        return usefulChunks.joinToString(separator = "") { it.text }
    }

}

class CommonProcessExecutionHandler(val afterProcessStartedCallback: () -> Unit = {}) {
    private val terminalEvents = AtomicProperty(listOf<TerminalOutputEvent>())
    private val terminalOutputCompletable = CompletableDeferred<TerminalOutput>()

    private var causeIfNotStarted: Throwable? = null

    val terminalOutput: Deferred<TerminalOutput>
        get() = terminalOutputCompletable

    val exitCode = CompletableDeferred<Int?>()

    suspend fun waitForProcessResult(): Either<Throwable, String> {
        val terminalOutput = terminalOutput.await()
        return causeIfNotStarted?.let { cause -> Left(cause) }
            ?: Right(terminalOutput.getText())
    }

    fun finishOutputCollecting() {
        terminalOutputCompletable.complete(
            TerminalOutput(terminalEvents.get())
        )
    }

    fun reportProcessNotStarted(cause: Throwable?) {
        causeIfNotStarted = cause
        finishOutputCollecting()
    }

    fun addStdout(text: String) {
        terminalEvents.add(TerminalOutputEvent(text, TerminalOutputType.STDOUT))
    }

    fun addStderr(text: String) {
        terminalEvents.add(TerminalOutputEvent(text, TerminalOutputType.STDERR))
    }

    val processLifetime = LifetimeDefinition()
}

fun <E> ObservableMutableProperty<List<E>>.add(element: E) = set(get() + element)
