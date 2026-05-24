package com.anonymous.benchmark.common.runner.agent

import com.anonymous.benchmark.common.utils.getOsInfo
import com.anonymous.benchmark.common.utils.trimAndPrependInnerBlock
import com.anonymous.benchmark.common.utils.getProjectDir
import com.intellij.openapi.project.Project
import com.intellij.openapi.vfs.toNioPathOrNull
import kotlin.io.path.absolutePathString
import kotlin.random.Random

private const val SHUFFLE_SEED = 42

class SimulatedUserUseCase(private val project: Project) {
    fun makeSystemPrompt(
        userKind: String,
        taskDescription: String,
        agentName: String
    ): String {
        val terminateToolName = TerminationTool.NAME
        val terminationPrompt =
            """
            After the agent finishes the task outlined in <task_description> section you should terminate the dialog via the `$terminateToolName` tool.
            1. **IMPORTANT**: In response to the first message from the agent you MUST **NEVER** terminate the dialogue; instead give the agent instructions according to your <task_description>.
            2. You must only call `$terminateToolName` if you decide the task is completed.
            3. Once you call `$terminateToolName`, the session is terminated. Until that the agent continues.
            4. You must strictly follow the precise schema for the tool.
            """

        val verbosityInstruction =
            """
            You must NEVER answer with more than 5 sentences. Typically, you should keep it within 1-2 sentences. Overall, optimize your answer against verbosity, don't waste words.
            """

        val agentInformation =
            """
            The $agentName Agent is an agentic AI coding assistant. It acts as a pair programming partner to a user, with the goal of resolving their task.
            """

        val systemPrompt =
            """
            Your purpose is to simulate a user of $agentName Agent, pursuing a task outlined in a <task_description> section.

            <agent_information>
            ${agentInformation.trimAndPrependInnerBlock()}
            </agent_information>

            As an input each turn you get:
              - all messages from the agent with trimmed corresponding tool calls
              - all the code diffs made by the agent
              - a trimmed list of compilation or runtime errors in the project

            Output instruction:
              - generally, you should send text messages that mimic a real user behavior. Act as if you are an engineer who wants to solve the task outlined in <task_description> section solely by means of chatting with the agent. This chat is your only output interface. Impersonate the user's character (see the <user_character> section). You must never ask the agent to do anything extra or tweak the requirements outlined in task_description: steering the agent towards the task while being in character is your only goal.
              - tools that the agent uses are not available to you: you are a mere user simulator. Your only tool is `$terminateToolName` that you should call once you see that the task is solved by the agent (similarly to how a real user would decide that their task has been solved).

            <dialog_termination>
            ${terminationPrompt.trimAndPrependInnerBlock()}
            </dialog_termination>

            You must adhere to behaviours typical for the user's character:
            <user_character>
            ${userKind.trimAndPrependInnerBlock()}
            ${verbosityInstruction.trimAndPrependInnerBlock()}
            </user_character>
            
            <task_description>
            ${taskDescription.trimAndPrependInnerBlock()}
            </task_description>

            <project_information>
            ${getOsInfo().trimAndPrependInnerBlock()}
            IDE: IntelliJ IDEA
            Project name: ${project.name}
            Project absolute path: ${project.getProjectDir()?.toNioPathOrNull()?.absolutePathString() ?: "unknown"}
            </project_information>
            """.trimIndent().trimMargin()

        return systemPrompt
    }
}

fun composeAgentTracePrompt(
    agentTrace: AgentTrace,
    numErrorsPerFile: Int = 5,
    isForJudge: Boolean = false,
    codeDiffCharsCap: Int = 60_000,
    unifiedCodeDiffsCharsCap: Int = 150_000,
): String {
    val codeDiffs =
        agentTrace.currCodeDiffs.joinToString(separator = "\n") { diff ->
            """
                **File path**: ${diff.path}
                **Code diff**:
                ${trimDiffForPrompt(diff.content, codeDiffCharsCap, isForJudge).trimAndPrependInnerBlock()}
                """.trimIndent().trimMargin()
        }

    val unifiedCodeDiffs = trimUnifiedDiffsForPrompt(codeDiffs, unifiedCodeDiffsCharsCap, isForJudge)

    val projectErrors =
        agentTrace.currProjectErrors.joinToString(separator = "\n\n") { fileErrors ->
            val errorsList = fileErrors.descriptions
                .shuffled(Random(SHUFFLE_SEED))
                .take(numErrorsPerFile)
                .joinToString(separator = "\n") { error ->
                    """
                        Line content: 
                        ${trimIfLongWithMessage(error.lineContent, trimLimit=250).trimAndPrependInnerBlock()}
                        Error message: 
                        ${trimIfLongWithMessage(error.errorMessage).trimAndPrependInnerBlock()}
                        """.trimIndent().trimMargin()
                }
            """
                **File path**: ${fileErrors.path}
                **List of $numErrorsPerFile randomly chosen errors in the file**:
                ${errorsList.trimAndPrependInnerBlock(1)}
                """.trimIndent().trimMargin()
        }

    val llmInstruction: String =
        if (isForJudge) "Check it to get a better sense of what the agent did."
        else "Since a real user would see this information, we hope it will help you simulate a real user more faithfully."

    val agentTracePrompt = """
            ${if (!isForJudge) "<agent_actions_summary>\n            " else ""}Here is a partial footprint of the agent's actions in the project. $llmInstruction We've gathered all the agent's code diffs in one place for your convenience: it is a full historical footprint of agent's actions. Some outputs were trimmed for you. Some fields might be empty.
            
            - Below you have all the code diffs made by the agent during the whole conversation.
            <code_diffs>
            ${unifiedCodeDiffs.trimAndPrependInnerBlock()}
            </code_diffs>
            
            - Below you have a brief representation of all the errors currently present in the project yielded by IntelliJ's static analysis. If it's empty there are no errors.
            <project_errors>
            ${projectErrors.trimAndPrependInnerBlock()}
            </project_errors>
            ${if (!isForJudge) "</agent_actions_summary>\n            " else ""}""".trimIndent().trimMargin()

    return agentTracePrompt
}

fun trimIfLongWithMessage(content: String, trimLimit: Int = 2000): String =
    if (content.length <= trimLimit) {
        content
    } else {
        "${content.take(trimLimit)}...\n(remaining characters are omitted **only from the User Simulator’s prompt** to reduce its context size)\n\n"
    }

private fun trimDiffForPrompt(diffContent: String, charLimit: Int, isForJudge: Boolean): String {
    if (diffContent.length <= charLimit) {
        return diffContent
    }

    val trimmed = diffContent.take(charLimit)

    val note = if (isForJudge) {
        """

        [BENCHMARK CONTEXT NOTICE — FOR THE LLM-JUDGE EVALUATING THIS TRAJECTORY]
        The diff above was truncated to approximately $charLimit tokens so that THIS benchmark prompt fits into the evaluator model’s context window.
        This truncation is a benchmark-only artifact (not real product behaviour). Do NOT treat missing diff content as agent failure and do NOT penalize the agent for it.
        """.trimIndent()
    } else {
        """

        [BENCHMARK CONTEXT NOTICE — FOR THE USER SIMULATOR]
        The diff above was truncated to approximately $charLimit tokens so that THIS benchmark prompt fits into the simulator model’s context window.
        This truncation is a benchmark-only artifact (not real product behaviour). Do NOT assess/grade the agent based on the missing part of the diff.
        """.trimIndent()
    }

    return "$trimmed\n\n... (diff trimmed; remaining content not shown) ...\n$note\n"
}

private fun trimUnifiedDiffsForPrompt(unifiedDiffsContent: String, charLimit: Int, isForJudge: Boolean): String {
    if (unifiedDiffsContent.length <= charLimit) {
        return unifiedDiffsContent
    }

    val trimmed = unifiedDiffsContent.take(charLimit)

    val note = if (isForJudge) {
        """

        [BENCHMARK CONTEXT NOTICE — FOR THE LLM-JUDGE EVALUATING THIS TRAJECTORY]
        The combined code_diffs section above was truncated to fit into the evaluator model’s context window.
        This truncation is a benchmark-only artifact (not real product behaviour). Do NOT treat missing diff content as agent failure and do NOT penalize the agent for it.
        """.trimIndent()
    } else {
        """

        [BENCHMARK CONTEXT NOTICE — FOR THE USER SIMULATOR]
        The combined code_diffs section above was truncated to fit into the simulator model’s context window.
        This truncation is a benchmark-only artifact (not real product behaviour). Do NOT assess/grade the agent based on the missing part of the diffs.
        """.trimIndent()
    }

    return "$trimmed\n\n... (combined code_diffs trimmed; remaining content not shown) ...\n$note\n"
}
