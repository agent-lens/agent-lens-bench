package com.anonymous.benchmark.common.runner.agent.preprocessor

import com.intellij.openapi.project.Project
import git4idea.repo.GitRepository
import kotlinx.serialization.Serializable


interface ScenarioPreprocessor {
    suspend fun prepareProject(project: Project, repo: GitRepository)
}
