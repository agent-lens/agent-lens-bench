package com.agentlens.benchmark.python.runner.agent.verifiers

import com.agentlens.benchmark.common.runner.agent.verifiers.VerifierResult
import com.agentlens.benchmark.common.utils.getProjectDir
import com.agentlens.benchmark.common.runner.agent.verifiers.AbstractTerminalCommandVerifier
import com.intellij.execution.configurations.GeneralCommandLine
import com.intellij.openapi.project.Project
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.io.File
import java.nio.file.Path
import kotlin.io.path.absolutePathString
import kotlin.io.path.exists
import kotlin.text.orEmpty

@Serializable
@SerialName("PythonRunTestsVerifier")
@Suppress("PROVIDED_RUNTIME_TOO_LOW")
data class PythonRunTestVerifier(
    @SerialName("command")
    val command: List<String>,
    @SerialName("working_directory")
    val workingDirectory: String? = null,
    @SerialName("venv_path")
    val venvPath: String? = DEFAULT_VENV_PATH,
    @SerialName("timeout_ms")
    override val timeoutMs: Long? = null
) : AbstractTerminalCommandVerifier() {

    override fun buildCommand(project: Project): List<String> = command

    override fun GeneralCommandLine.commandSetup(project: Project): GeneralCommandLine? {
        val projectDir = getProjectDir(project)
        val workDirectory = this@PythonRunTestVerifier.workingDirectory
            ?.let { projectDir.resolve(it).normalize() }
            ?: projectDir

        withWorkDirectory(workDirectory.absolutePathString())

        val resolvedVenvPath = venvPath
            ?.takeIf(String::isNotBlank)
            ?.let { projectDir.resolve(it).normalize() }
            ?.takeIf(Path::exists)
            ?: return null

        val executablesDirectory = resolvedVenvPath.resolve(VENV_EXECUTABLES_DIRECTORY).absolutePathString()
        val currentPath = environment[PATH_ENV].orEmpty()

        withEnvironment(VIRTUAL_ENV, resolvedVenvPath.absolutePathString())
        withEnvironment(
            PATH_ENV,
            listOf(executablesDirectory, currentPath)
                .filter(String::isNotBlank)
                .joinToString(separator = File.pathSeparator)
        )

        return this
    }

    override fun parseSuccessResult(output: String): VerifierResult {
        val (expected, failed) = parsePytestResult(output) ?: parseUnittestResult(output)
        ?: return VerifierResult.Failure("Unable to parse Python test output")

        return if (failed == 0) {
            VerifierResult.SuccessWithMetrics(metrics = buildJsonObject {
                put("tests", expected)
                put("passed", expected)
            })
        } else {
            VerifierResult.Failure("Some tests failed, ${expected - failed} tests passed out of $expected")
        }
    }

    private fun parsePytestResult(output: String): TestRunResult? {
        val match = PYTEST_RESULT_REGEX.find(output) ?: return null
        val failed = match.groupValues[1].toIntOrNull() ?: 0
        val passed = match.groupValues[2].toIntOrNull() ?: 0

        return TestRunResult(expected = failed + passed, failed = failed)
    }

    private fun parseUnittestResult(output: String): TestRunResult? {
        val expected = UNITTEST_RESULT_REGEX.find(output)?.groupValues?.get(1)?.toIntOrNull() ?: return null
        val failureDetails = UNITTEST_FAILURE_REGEX.find(output)?.groupValues?.get(1).orEmpty()
        val failed = UNITTEST_FAILURE_COUNT_REGEX.findAll(failureDetails)
            .sumOf { it.groupValues[1].toIntOrNull() ?: 0 }

        return TestRunResult(expected = expected, failed = failed)
    }

    private data class TestRunResult(
        val expected: Int,
        val failed: Int
    )

    companion object {
        private const val DEFAULT_VENV_PATH = ".venv"
        private const val PATH_ENV = "PATH"
        private const val VIRTUAL_ENV = "VIRTUAL_ENV"
        private const val VENV_EXECUTABLES_DIRECTORY = "bin"

        private val PYTEST_RESULT_REGEX = Regex("(?:(\\d+)\\s+failed,\\s+)?(?:(\\d+)\\s+passed)")

        private val UNITTEST_RESULT_REGEX = Regex("Ran\\s+(\\d+)\\s+tests?")
        private val UNITTEST_FAILURE_REGEX = Regex("FAILED\\s+\\(([^)]*)\\)")
        private val UNITTEST_FAILURE_COUNT_REGEX = Regex("(?:failures|errors)=(\\d+)")
    }
}
