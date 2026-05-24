package com.anonymous.benchmark.runner.agent.preprocessor

import com.anonymous.benchmark.common.runner.agent.preprocessor.ScenarioPreprocessor
import com.anonymous.benchmark.utils.resolvePsiClass
import com.intellij.openapi.application.writeAction
import com.intellij.openapi.project.Project
import git4idea.commands.Git
import git4idea.commands.GitCommand
import git4idea.commands.GitLineHandler
import git4idea.repo.GitRepository
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

private val logger = mu.KotlinLogging.logger {}

@Serializable
@SerialName("RemoveTestClassPreprocessor")
@Suppress("PROVIDED_RUNTIME_TOO_LOW")
data class RemoveTestClassPreprocessor(val relativePathToTest: String, val classFullyQualifiedName: String):
    ScenarioPreprocessor {

    @Suppress("UnstableApiUsage")
    override suspend fun prepareProject(project: Project, repo: GitRepository) {
        val testClass = project.resolvePsiClass(relativePathToTest, classFullyQualifiedName) ?: error("Cannot find test class")

        logger.info { "Deleting existing test class file..." }
        writeAction {
            testClass.delete()
        }

        val git = Git.getInstance()
        git.runCommand(GitLineHandler(project, repo.root, GitCommand.ADD).apply {
            addParameters("-A")
        })

        val commitMessage = "Delete existing test class $classFullyQualifiedName"
        git.runCommand(GitLineHandler(project, repo.root, GitCommand.COMMIT).apply {
            addParameters("-m", commitMessage)
        })
    }
}
