package com.agentlens.benchmark.runner.agent.verifiers

import com.agentlens.benchmark.common.runner.agent.verifiers.VerifierResult
import com.agentlens.benchmark.common.utils.getProjectDir
import com.agentlens.benchmark.common.runner.agent.verifiers.AbstractTerminalCommandVerifier
import com.intellij.execution.configurations.GeneralCommandLine
import com.intellij.openapi.project.Project
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlin.io.path.absolutePathString

@Serializable
@SerialName("JavaRunTestsVerifier")
@Suppress("PROVIDED_RUNTIME_TOO_LOW")
data class JavaRunTestsVerifier(
    @SerialName("build_system_name")
    val buildSystemName: String = MAVEN_BUILD_SYSTEM,
    @SerialName("working_directory")
    val workingDirectory: String? = null,
    @SerialName("test_pattern")
    val testPattern: String? = null,
    @SerialName("command")
    val command: List<String> = listOf("test"),
    @SerialName("timeout_ms")
    override val timeoutMs: Long? = null,

    // TODO: Coverage
    @SerialName("source_path")
    val sourcePath: String? = null,
    @SerialName("source_class_name")
    val sourceClassName: String? = null
) : AbstractTerminalCommandVerifier() {

    override fun buildCommand(project: Project): List<String> =
        when (buildSystemName) {
            MAVEN_BUILD_SYSTEM ->
                buildList {
                    addAll(command)
                    testPattern?.let { add("-Dtest=$it") }
                }
            GRADLE_BUILD_SYSTEM ->
                buildList {
                    addAll(command)
                    testPattern?.also {
                        add("--tests")
                        add(it)
                    }
                }
            else -> error(
                "Unsupported build system `$buildSystemName`. Expected `$MAVEN_BUILD_SYSTEM` or `$GRADLE_BUILD_SYSTEM`"
            )
        }

    override fun GeneralCommandLine.commandSetup(project: Project): GeneralCommandLine {
        val projectDir = getProjectDir(project)
        val workDirectory = this@JavaRunTestsVerifier.workingDirectory
            ?.let { projectDir.resolve(it).normalize() }
            ?: projectDir

        withWorkDirectory(workDirectory.absolutePathString())
        return this
    }

    override fun parseSuccessResult(output: String): VerifierResult {
        val result = parseMavenTestRunResult(output) ?: parseGradleTestRunResult(output)
            ?: return VerifierResult.Failure("Unable to parse test output")

        return if (result.failed == 0) {
            VerifierResult.SuccessWithMetrics(metrics = result.toMetrics())
        } else {
            VerifierResult.Failure(
                "Some tests failed, ${result.passed} tests passed out of ${result.tests}. " +
                    "Failed: ${result.failed}, skipped: ${result.skipped}"
            )
        }
    }

    private fun parseMavenTestRunResult(output: String): TestRunResult? {
        val match = MAVEN_TESTS_RESULT_REGEX.findAll(output).lastOrNull() ?: return null
        return TestRunResult(
            tests = match.toInt(1),
            failed = match.toInt(2) + match.toInt(3),
            skipped = match.toInt(4)
        )
    }

    private fun parseGradleTestRunResult(output: String): TestRunResult? {
        val match = GRADLE_TESTS_RESULT_REGEX.find(output) ?: return null
        return TestRunResult(
            tests = match.toInt(1),
            failed = match.toInt(2),
            skipped = match.toInt(3)
        )
    }

    private fun MatchResult.toInt(ix: Int): Int = groupValues[ix].toIntOrNull() ?: 0

    private fun TestRunResult.toMetrics() = buildJsonObject {
        put("tests", tests)
        put("passed", passed)
        put("failed", failed)
        put("skipped", skipped)
    }

    private data class TestRunResult(
        val tests: Int,
        val failed: Int,
        val skipped: Int
    ) {
        val passed: Int = tests - failed - skipped
    }

    companion object {
        private const val MAVEN_BUILD_SYSTEM = "maven"
        private const val GRADLE_BUILD_SYSTEM = "gradle"

        private val MAVEN_TESTS_RESULT_REGEX = Regex(
            "Tests run:\\s*(\\d+),\\s*Failures:\\s*(\\d+),\\s*Errors:\\s*(\\d+),\\s*Skipped:\\s*(\\d+)"
        )
        private val GRADLE_TESTS_RESULT_REGEX = Regex(
            "(\\d+)\\s+tests? completed(?:,\\s*(\\d+)\\s+failed)?(?:,\\s*(\\d+)\\s+skipped)?"
        )
    }
}
