package com.agentlens.benchmark.common.runner.agent


object TerminationTool {
    const val NAME: String = "terminate_dialog"
    val description: String = """
        Terminates the dialog with the agent.
        Call this tool when you decide that your task was successfully completed by the agent.
    """.trimIndent()

    val termination_tool_schema = """
        {
            "type":"object",
            "properties": {
                "termination_reason": {
                    "type": "string",
                    "description": "Reason for terminating the dialog in 1-3 sentences."
                }
            },
            "required": ["termination_reason"]
        }""".trimIndent()
}
