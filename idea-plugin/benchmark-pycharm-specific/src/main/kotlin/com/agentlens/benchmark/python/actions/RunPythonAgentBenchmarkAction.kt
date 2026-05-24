package com.agentlens.benchmark.python.actions

import com.agentlens.benchmark.python.runner.agent.PythonAgentBenchmarkRunner
import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent

class RunPythonAgentBenchmarkAction : AnAction() {
    override fun actionPerformed(actionEvent: AnActionEvent) {
        PythonAgentBenchmarkRunner.getInstance().runForAllProjects()
    }
}
