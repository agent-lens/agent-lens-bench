package com.agentlens.benchmark.actions

import com.agentlens.benchmark.runner.agent.JavaAgentBenchmarkRunner
import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent

class RunAgentBenchmarkAction : AnAction() {
    override fun actionPerformed(actionEvent: AnActionEvent) {
        JavaAgentBenchmarkRunner.getInstance().runForAllProjects()
    }
}
