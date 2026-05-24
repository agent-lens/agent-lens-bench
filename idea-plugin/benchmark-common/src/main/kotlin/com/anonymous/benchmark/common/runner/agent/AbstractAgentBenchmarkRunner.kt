package com.anonymous.benchmark.common.runner.agent

import com.anonymous.benchmark.common.schema.Message
import com.anonymous.benchmark.common.schema.MessageKind
import com.anonymous.benchmark.common.schema.LlmUsage
import com.anonymous.benchmark.common.dialogs.AgentSettings
import com.anonymous.benchmark.common.dialogs.AgentSettingsDialog
import com.anonymous.benchmark.common.runner.agent.engine.AgentEngine
import com.anonymous.benchmark.common.runner.agent.engine.ExternalAgentEngine
import com.anonymous.benchmark.common.runner.agent.verifiers.VerifierResult
import com.anonymous.benchmark.common.runner.getBenchJson
import com.anonymous.benchmark.common.schema.AgentBenchmarkResults
import com.anonymous.benchmark.common.schema.AgentConfig
import com.anonymous.benchmark.common.schema.AgentFailureResult
import com.anonymous.benchmark.common.schema.AgentProjectResults
import com.anonymous.benchmark.common.schema.AgentResult
import com.anonymous.benchmark.common.schema.AgentScenario
import com.anonymous.benchmark.common.schema.AgentScenario.Companion.buildScenarioFromPath
import com.anonymous.benchmark.common.schema.AgentSuccessResult
import com.anonymous.benchmark.common.schema.BenchmarkRunInfo
import com.anonymous.benchmark.common.utils.ErrorCapturingLogger
import com.anonymous.benchmark.common.utils.getResourceText
import com.anonymous.benchmark.common.utils.getSha256Hash
import com.anonymous.benchmark.common.utils.JsonUtils
import com.anonymous.benchmark.common.schema.UserRequest
import com.anonymous.benchmark.common.utils.showNotificationToUser
import com.anonymous.benchmark.common.utils.buildSystem.IdeBuildSystem
import com.anonymous.benchmark.common.utils.catchExceptions
import com.anonymous.benchmark.common.utils.encodeToStringCompat
import com.intellij.execution.ExecutionManager
import com.intellij.ide.GeneralSettings
import com.intellij.notification.NotificationType
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.application.EDT
import com.intellij.openapi.fileEditor.FileEditorManager
import com.intellij.openapi.progress.EmptyProgressIndicator
import com.intellij.openapi.project.DumbService
import com.intellij.openapi.project.Project
import com.intellij.openapi.project.ProjectManager
import com.anonymous.benchmark.common.utils.getProjectDir
import com.intellij.openapi.project.waitForSmartMode
import com.intellij.openapi.ui.Messages
import com.intellij.openapi.vcs.ProjectLevelVcsManager
import com.intellij.openapi.vcs.VcsConfiguration
import com.intellij.openapi.vcs.VcsShowConfirmationOption
import com.intellij.openapi.vfs.LocalFileSystem
import com.intellij.openapi.vfs.VfsUtil
import com.intellij.openapi.vfs.resolveFromRootOrRelative
import com.intellij.openapi.wm.ToolWindowManager
import com.intellij.platform.PlatformProjectOpenProcessor
import com.intellij.platform.ide.progress.withBackgroundProgress
import com.intellij.platform.util.progress.forEachWithProgress
import com.intellij.platform.util.progress.withProgressText
import com.intellij.util.WaitFor
import com.intellij.vcs.log.Hash
import com.intellij.vcs.log.impl.HashImpl
import git4idea.GitVcs
import git4idea.commands.Git
import git4idea.commands.GitCommand
import git4idea.commands.GitLineHandler
import git4idea.repo.GitRepository
import git4idea.repo.GitRepositoryManager
import git4idea.reset.GitResetMode
import git4idea.reset.GitResetOperation
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.channelFlow
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onCompletion
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.ExperimentalSerializationApi
import kotlinx.serialization.json.decodeFromStream
import kotlinx.serialization.json.encodeToStream
import mu.KotlinLogging
import org.jetbrains.plugins.terminal.TerminalToolWindowFactory
import org.jetbrains.plugins.terminal.TerminalToolWindowManager
import java.nio.file.Path
import java.nio.file.Paths
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import kotlin.collections.forEach
import kotlin.io.path.ExperimentalPathApi
import kotlin.io.path.Path
import kotlin.io.path.createDirectories
import kotlin.io.path.createDirectory
import kotlin.io.path.createTempDirectory
import kotlin.io.path.createTempFile
import kotlin.io.path.deleteRecursively
import kotlin.io.path.exists
import kotlin.io.path.inputStream
import kotlin.io.path.isRegularFile
import kotlin.io.path.listDirectoryEntries
import kotlin.io.path.name
import kotlin.io.path.nameWithoutExtension
import kotlin.io.path.outputStream
import kotlin.io.path.pathString
import kotlin.io.path.readText
import kotlin.io.path.writeText
import kotlin.time.Duration.Companion.seconds
import kotlin.time.measureTime
import kotlinx.serialization.encodeToString as encodeToStringCompatibility

const val SUMMARY_FILE_PREFIX = "summary"

val logger = ErrorCapturingLogger(KotlinLogging.logger { })

data class UsageHolder(var usage: LlmUsage)

abstract class AbstractAgentBenchmarkRunner(
    protected val scope: CoroutineScope,
) {
    private val usageHolder = UsageHolder(LlmUsage())

    private var lastSettings: AgentSettings? = null
    private val defaultConfigPath: String = "config/agent/general.json"

    private val projectReloadAttempts = 3


    protected suspend fun syncBuildSystem(project: Project, force: Boolean) {
        try {
            IdeBuildSystem.refreshBuildSystemIfRequired(project, forceRefresh = force)
        } catch (ex: Throwable) {
            logger.error(ex) { ex.message }
        }
    }

    @OptIn(ExperimentalSerializationApi::class)
    protected fun getExistingResults(whereToSearch: Path): AgentBenchmarkResults? =
        whereToSearch
            .listDirectoryEntries()
            .asSequence()
            .filter { it.isRegularFile() && it.name.startsWith(SUMMARY_FILE_PREFIX) }
            .mapNotNull { path ->
                path.inputStream().use { input ->
                    logger.catchExceptions {
                        getBenchJson().decodeFromStream<AgentBenchmarkResults>(input)
                    }.getOrNull()
                }
            }
            .maxByOrNull { result ->
                // Be defensive: if timestamp parsing fails, treat as minimal value
                logger.catchExceptions { LocalDateTime.parse(result.timestamp) }.getOrNull()
                    ?: LocalDateTime.MIN
            }

    protected fun setOpenProjectSameWindow() {
        GeneralSettings.getInstance().confirmOpenNewProject = GeneralSettings.OPEN_PROJECT_SAME_WINDOW
    }

    protected fun showProjectCompletion(project: Project, budgetDollarsLimit: Float) {
        val totalPrice = usageHolder.usage.price
        val message = "Benchmark completed, spent ${"%.3f".format(totalPrice)}$." +
                (if (totalPrice >= budgetDollarsLimit) "(limit ${budgetDollarsLimit}$ exceeded)" else "")

        if (ApplicationManager.getApplication().isHeadlessEnvironment) {
            logger.info { message }
            return
        }

        project.showNotificationToUser(
            this.scope,
            message = message,
            type = NotificationType.INFORMATION
        )
    }

    @OptIn(ExperimentalSerializationApi::class)
    protected fun getConfig(configFilePath: String?): AgentConfig {
        val configText = configFilePath
            ?.let { Paths.get(it).takeIf { file -> file.isRegularFile() } }
            ?.readText()
            ?: getResourceText(configFilePath.takeIf { !it.isNullOrBlank() } ?: defaultConfigPath)
            ?: error("Failed to read config at path '$defaultConfigPath'")
        val config = logger.catchExceptions {
            getBenchJson().decodeFromString<AgentConfig>(configText)
        }.onFailure { exception ->
            if (ApplicationManager.getApplication().isHeadlessEnvironment) {
                logger.error(exception) { "Can't decode config in headless mode" }
            } else {
                Messages.showErrorDialog(
                    exception.message ?: "Can't decode config",
                    "Config Decode Error"
                )
            }
        }.getOrThrow()
        return config
    }

    protected fun getGitRepo(currentProject: Project): GitRepository {
        val containingVirtualFile = currentProject.getProjectDir()
            ?: error("Failed to get project root directory for project ${currentProject.name}")

        val gitRepositoryManager = GitRepositoryManager.getInstance(currentProject)
        object : WaitFor(10000) {
            override fun condition() = gitRepositoryManager.getRepositoryForFile(containingVirtualFile) != null
        }

        val repo = gitRepositoryManager.getRepositoryForFile(containingVirtualFile)
            ?: error("No git repository found")

        return repo
    }

    protected fun enableSilentGitAutoAdd(project: Project) {
        val vcsManager = ProjectLevelVcsManager.getInstance(project)
        vcsManager.getStandardConfirmation(
            VcsConfiguration.StandardConfirmation.ADD,
            GitVcs.getInstance(project)
        ).value = VcsShowConfirmationOption.Value.DO_ACTION_SILENTLY
    }

    protected suspend fun callGitHardReset(
        project: Project,
        repo: GitRepository,
        repoHash: Hash,
        branch: String,
    ) = withProgressText("Hard resetting to revision $repoHash on branch $branch") {
        changeGitBranch(project, repo, branch)
        val result = GitResetOperation(
            project, mapOf(repo to repoHash), GitResetMode.HARD, EmptyProgressIndicator()
        ).execute()
        check(result) { "Can't reset to revision $repoHash on branch $branch" }
        waitForReindexing(project)
    }

    private fun changeGitBranch(project: Project, repo: GitRepository, branch: String) {
        val root = repo.root
        val handler = GitLineHandler(project, root, GitCommand.CHECKOUT)
        handler.addParameters("-f", branch)

        Git.getInstance().runCommand(handler)

        try {
            VfsUtil.markDirtyAndRefresh(true, true, true, root)
        } catch (e: Exception) {
            logger.error { "VFS refresh failed with an exception: ${e.message}" }
        }
    }

    private fun waitForReindexing(project: Project) {
        val dumbService = DumbService.getInstance(project)
        object : WaitFor(2000) {
            override fun condition() = dumbService.isDumb
        }
        dumbService.waitForSmartMode()
    }

    suspend fun openProject(path: String): Project? {
        val virtualFile = LocalFileSystem.getInstance()
            .refreshAndFindFileByPath(path) ?: return null

        // opening project this way ensures ProjectRootManager.getInstance(project).contentRoots is not empty
        // it is necessary for complete [FileIndex] and agent ability to use read and write tools
        return PlatformProjectOpenProcessor.getInstance()
            .openProjectAsync(virtualFile, projectToClose = null, forceOpenInNewFrame = false)
    }

    fun runForAllProjects() {
        val isHeadless = ApplicationManager.getApplication().isHeadlessEnvironment
        AgentEnvService.validate(isHeadless)

        if (isHeadless) {
            try {
                runHeadless()
                return
            } catch (ex: Throwable) {
                logger.error(ex) { ex.message }

                logger.info { "Exiting because of issue..." }
                // shutdown app
                ApplicationManager.getApplication().exit(true, true, false, 1)
                return
            }
        }

        val settingsDialog = AgentSettingsDialog(lastSettings)
        if (!settingsDialog.showAndGet()) return

        val settings = settingsDialog.getAgentSettings()
        lastSettings = settings

        runInternal(settings)
    }

    private fun runHeadless() {
        val settings = AgentSettings(
            taskName = AgentEnvService.getEnvValue(EnvVariable.EXP_NAME) ?: "unknown",
            configFilePath = AgentEnvService.getEnvValue(EnvVariable.CONFIG_FILE_PATH),
            whereToSaveDumpsDirectory = AgentEnvService.getEnvValue(EnvVariable.WHERE_TO_SAVE_DUMPS) ?: error("Specify environment variable: ${EnvVariable.WHERE_TO_SAVE_DUMPS}"),
            clearFolder = AgentEnvService.getEnvValue(EnvVariable.CLEAR_FOLDER)?.toBoolean() ?: false,
            useAllUsers = AgentEnvService.getEnvValue(EnvVariable.USE_ALL_USERS)?.toBoolean() ?: true,
            projectsRootPath = AgentEnvService.getEnvValue(EnvVariable.PROJECTS_ROOT_DIR) ?: error("Specify environment variable: ${EnvVariable.PROJECTS_ROOT_DIR}"),
            providerName = AgentEnvService.getEnvValue(EnvVariable.PROVIDER_NAME) ?: error("Specify environment variable: ${EnvVariable.PROVIDER_NAME}"),
            modelName = AgentEnvService.getEnvValue(EnvVariable.MODEL_NAME) ?: "",
            modelUrl = AgentEnvService.getEnvValue(EnvVariable.MODEL_URL),
            agentEngineUrl = AgentEnvService.getEnvValue(EnvVariable.AGENT_ENGINE_URL)
        )

        runInternal(settings, exitOnFinish = true)
    }

    @OptIn(ExperimentalPathApi::class)
    private fun runInternal(settings: AgentSettings, exitOnFinish: Boolean = false) {
        val whereToSaveDumps = Paths.get(settings.whereToSaveDumpsDirectory)
        whereToSaveDumps.takeIf { !it.exists() }?.createDirectories()

        if (settings.clearFolder) {
            whereToSaveDumps.apply {
                deleteRecursively()
                createDirectory()
            }
        }

        val config = getConfig(settings.configFilePath).let { config ->
            val actualEngine = if (!settings.agentEngineUrl.isNullOrEmpty()) {
                ExternalAgentEngine(settings.agentEngineUrl)
            } else config.agentEngine
            config.copy(
                userPaths = if (settings.useAllUsers) config.userPaths else config.userPaths.take(1),
                agentEngine = actualEngine
            )
        }

        val projectScenarios = config.scenarioPaths.map { buildScenarioFromPath(it) }.groupBy { it.projectPath }
        val userDescriptions = config.userPaths.associate { userPath ->
            val userDescription = getResourceText(userPath)
                ?: error("Failed to read user description at path '$userPath'")
            Path(userPath).nameWithoutExtension to userDescription
        }

        setOpenProjectSameWindow()

        scope.launch(Dispatchers.Default) {
            try {
                // load corresponding model
                val modelName = config.agentEngine.initModelProviderBeforeBenchmarkRun(settings.getModelSettings())
                config.agentEngine.initBeforeBenchmarkRun()

                val runInfo = createRunInfo(settings, config, modelName)
                projectScenarios.forEach { (projectPath, scenarios) ->
                    val joinWith = getExistingResults(whereToSaveDumps) ?: AgentBenchmarkResults()
                    // Trying to read from env first, falling back to json config
                    val projectsRootPath = settings.projectsRootPath
                    val fullProjectPath = Path(projectsRootPath).resolve(projectPath).pathString

                    var attempt = 0
                    var currentProject: Project? = null
                    while (attempt < projectReloadAttempts && currentProject == null) {
                        currentProject = loadProject(fullProjectPath)
                        ++attempt
                    }

                    if (currentProject == null) {
                        logger.error { "Failed to load project at path '$fullProjectPath' after $attempt attempts" }
                        if (ApplicationManager.getApplication().isHeadlessEnvironment) {
                            ApplicationManager.getApplication().exit(true, true, false, 1)
                        }
                    } else {
                        runForProject(
                            currentProject, scenarios, userDescriptions, config, whereToSaveDumps, joinWith, runInfo
                        ).join()
                    }
                }
            } catch (ex: Throwable) {
                logger.error(ex) { ex.message }
            }

            if (exitOnFinish) {
                val app = ApplicationManager.getApplication()
                app.invokeLater {
                    app.exit(true, true, false)
                }
            }
        }
    }

    open suspend fun loadProject(projectPath: String): Project? {
        val projectManager = ProjectManager.getInstance()

        if (Path(projectPath).exists()) {
            logger.info { "Opening project at: $projectPath" }
        } else {
            logger.error { "Path to project '$projectPath' doesn't exist" }
            return null
        }

        val project = projectManager.openProjects.firstOrNull {
            it.getProjectDir()?.path == projectPath
        } ?: withContext(Dispatchers.Default) { openProject(projectPath)!! }

        project.waitForSmartMode()

        syncBuildSystem(project, true)

        if (project.getProjectDir() == null) {
            logger.error { "Failed to get project root, closing the project '${project.name}'" }
            projectManager.closeAndDispose(project)
            return null
        }

        return project
    }



    @OptIn(ExperimentalSerializationApi::class)
    private fun runForProject(
        currentProject: Project,
        scenarios: List<AgentScenario>,
        userDescriptions: Map<String, String>,
        config: AgentConfig,
        whereToSaveDumps: Path,
        joinWith: AgentBenchmarkResults,
        runInfo: BenchmarkRunInfo,
    ): Job {
        val budgetDollarsLimit = config.budgetDollarsLimit
        val existingResults = joinWith.projectsResults
            .filter { it.projectTitle == currentProject.name }
            .flatMap { it.results }
            .filterIsInstance<AgentSuccessResult>()
        val resultsExist = joinWith.projectsResults.any { it.projectTitle == currentProject.name }
        var path: Path? = null
        return currentProject
            .runForScenariosFlow(scenarios, userDescriptions, whereToSaveDumps, config, existingResults)
            .onEach { projectResults ->
                if (path == null) {
                    path = createTempFile(whereToSaveDumps, SUMMARY_FILE_PREFIX, ".json")
                }

                val results = if (!resultsExist) {
                    joinWith.projectsResults + projectResults
                } else {
                    joinWith.projectsResults.map {
                        if (it.projectTitle == currentProject.name)
                            projectResults.copy(results = existingResults + projectResults.results)
                        else it
                    }
                }

                val benchmarkResults = AgentBenchmarkResults(
                    timestamp = LocalDateTime.now().toString(),
                    runInfo = runInfo,
                    projectsResults = results,
                )

                path.outputStream().use { stream ->
                    getBenchJson().encodeToStream(benchmarkResults, stream)
                }
            }
            .onCompletion { showProjectCompletion(currentProject, budgetDollarsLimit) }
            .catch { logger.error(it) { "Exception during benchmarking project: ${currentProject.name}" }}
            .launchIn(scope)
    }

    private fun Project.runForScenariosFlow(
        scenarios: List<AgentScenario>,
        userDescriptions: Map<String, String>,
        whereToSaveDumps: Path,
        config: AgentConfig,
        existingResults: List<AgentResult>,
    ): Flow<AgentProjectResults> = channelFlow {
        val repo = getGitRepo(this@runForScenariosFlow)
        enableSilentGitAutoAdd(this@runForScenariosFlow)

        val results = mutableListOf<AgentResult>()
        usageHolder.usage = LlmUsage()
        withBackgroundProgress(this@runForScenariosFlow, "Running Benchmarks") {
            logger.info("Running Benchmarks...")

            scenarios.forEach { scenario ->
                val scenarioName = Path(scenario.scenarioPath).nameWithoutExtension
                userDescriptions.filterKeys { userName ->
                    existingResults.none { result ->
                         result.scenarioName == scenarioName && result.simulatorName == userName
                    }
                }.toList().zipWithIndex().forEachWithProgress { indexedUser ->
                    withProgressText("Scenario ${scenario.scenarioPath}; User ${indexedUser.index}") {
                        logger.info("Scenario ${scenario.scenarioPath}; User ${indexedUser.index}")

                        if (usageHolder.usage.price >= config.budgetDollarsLimit) {
                            logger.error { "Price limit has been exceeded: ${usageHolder.usage.price}" }
                            // Skip rest of the points if the limit is exceeded
                            return@withProgressText
                        }

                        val (userName, userDescription) = indexedUser.value
                        val messageDir = createTempDirectory(whereToSaveDumps, "${scenarioName}-${userName}-")
                        val messagePath = messageDir.nameWithoutExtension

                        try {
                            logger.clearCapturedErrors()

                            val repoHash = HashImpl.build(scenario.repoHash ?: config.defaultRepoHash)
                            val branch = scenario.branch ?: config.defaultBranch
                            callGitHardReset(this@runForScenariosFlow, repo, repoHash, branch)

                            stopAllRunningProcesses()

                            scenario.preprocessors.forEach {
                                it.prepareProject(this@runForScenariosFlow, repo)
                            }

                            syncBuildSystem(this@runForScenariosFlow, false)

                            openScenarioFiles(this@runForScenariosFlow, scenario)
                            closeTerminalTabs(this@runForScenariosFlow)

                            results += this@runForScenariosFlow.runUserAgentLoop(
                                scenario = scenario,
                                scenarioName = scenarioName,
                                userName = userName,
                                userDescription = userDescription,
                                agentEngine = config.agentEngine,
                                messageDir = messageDir,
                                messagePath = messagePath
                            )

                            send(AgentProjectResults(this@runForScenariosFlow.name, results))
                        } catch (e: Exception) {
                            logger.error(e) { "User-agent loop failed on scenario \"$scenarioName\" with exception" }

                            results += AgentFailureResult(
                                scenarioName = scenarioName,
                                simulatorName = userName,
                                messagePath = messagePath,
                                errors = logger.getCapturedErrors(),
                                failureReason = e.message,
                            )

                            send(AgentProjectResults(this@runForScenariosFlow.name, results))
                        }
                    }
                }
            }
        }
    }

    private suspend fun Project.runUserAgentLoop(
        scenario: AgentScenario,
        scenarioName: String,
        userName: String,
        userDescription: String,
        agentEngine: AgentEngine,
        messageDir: Path,
        messagePath: String
    ): AgentSuccessResult {
        val user = SimulatedUser.create(
            userDescription,
            scenario.userInstruction,
            this,
            agentEngine is ExternalAgentEngine,
            agentEngine.getAgentName()
        )

        val chatHistory = mutableListOf(Message.assistant("The agent is initialised and is waiting for instructions."))
        if (scenario.fixedFstUserMessage) {
            if (scenario.firstUserMessage.isEmpty())
                error("Failed to load the first user message, it's empty: ${scenario.scenarioPath}")
            chatHistory.add(Message.user(scenario.firstUserMessage))
        }
        agentEngine.initBeforeScenarioRun(this, chatHistory, scenario.getAgentSettings())

        var terminationReason = "Reached the limit of user messages"
        var terminated = false
        try {
            val totalTimePerScenario = measureTime {
                try {
                    withTimeout(scenario.scenarioTimeoutSeconds.seconds) {
                        for (i in 0 until scenario.maxSteps) {
                            generateNextChatIteration(chatHistory, user, agentEngine, messageDir, scenario.agentTurnTimeoutSeconds)?.let {
                                terminationReason = it
                                terminated = true
                            }

                            if (terminated) {
                                break
                            }
                        }
                    }
                } catch (_: TimeoutCancellationException) {
                    terminationReason = "Scenario timed out after ${scenario.scenarioTimeoutSeconds}s"
                    logger.catchExceptions {
                        user.generateNext(chatHistory, messageDir)
                    }
                    logger.catchExceptions {
                        agentEngine.forceTerminateScenarioRun()
                    }
                }
            }

            val verifierResults = scenario.verifiers.map { verifier ->
                try {
                    // Wait until verifier are finished
                    withTimeout(scenario.verifierTimeoutSeconds.seconds) {
                        verifier.verify(this@runUserAgentLoop, scenario.scenarioPath, chatHistory)
                    }
                } catch (e: TimeoutCancellationException) {
                    VerifierResult.Failure("Verifier timed out after ${scenario.verifierTimeoutSeconds} seconds")
                } catch (e: Exception) {
                    VerifierResult.Failure("Verifier failed with an exception: ${e.message}")
                }
            }

            val usages = agentEngine.getUsages()

            return AgentSuccessResult(
                scenarioName = scenarioName,
                simulatorName = userName,
                messagePath = messagePath,
                errors = logger.getCapturedErrors(),
                taskDescription = scenario.userInstruction,
                formalVerificationResult = if (verifierResults.all { it.isSuccess() }) 1 else 0,
                terminationReason = terminationReason,
                agentBenchTags = scenario.tags,
                verifierResults = verifierResults,
                agentTracePrompt = composeAgentTracePrompt(user.getAgentTrace(), isForJudge = true),
                agentPrice =usages.map { it.price },
                agentTime =usages.map { it.time },
                agentInputTokens =usages.map { it.inputTokens },
                agentGenerationTokens =usages.map { it.generationTokens },
                agentPromptCacheHitTokens =usages.map { it.promptCacheHitTokens },
                agentToolCallsNum =usages.map { it.toolCallsNumber },
                agentMessagesPerTurn = usages.map { it.inputTokens.size },
                agentInteractionTotalTime = totalTimePerScenario.inWholeMinutes,
            )
        } finally {
            messageDir.resolve("agent_chat_dump.json").writeText(agentEngine.getChatDump())
            messageDir.resolve("tool_calls_dump.json").writeText(
                JsonUtils.prettyJson.encodeToStringCompat(
                    agentEngine.getToolCallsDump().associate {
                        it.assistantMessageIndex to it.calls
                    }
                )
            )
        }
    }

    private suspend fun generateNextChatIteration(
        chatHistory: MutableList<Message>,
        user: SimulatedUser,
        agentEngine: AgentEngine,
        messageDir: Path,
        timeoutSeconds: Long
    ): String? {
        val request = if (chatHistory.last().type == MessageKind.USER) {
            UserRequest(chatHistory.last().text)
        } else {
            val userResponse = user.generateNext(chatHistory, messageDir)
                ?: return "No agent actions since last user message"
            usageHolder.usage += userResponse.usage
            chatHistory.add(Message.user(userResponse.response))

            if (userResponse.toolCalls.firstOrNull()?.name == TerminationTool.NAME) {
                return "User decided to finish the dialog"
            }

            UserRequest(userResponse.response)
        }

        try {
            agentEngine.sendRequestWithTimeout(request, timeoutSeconds)
        } catch (e: TimeoutCancellationException) {
            val terminationReason = "Waiting for the agent response timed out after ${timeoutSeconds}s"
            logger.catchExceptions {
                user.generateNext(chatHistory, messageDir)
            }
            return terminationReason
        } catch (e: Exception) {
            val terminationReason = "Agent iteration failed with an unexpected exception: ${e.message}"
            logger.error(e) { terminationReason }
            logger.catchExceptions {
                user.generateNext(chatHistory, messageDir)
            }
            return terminationReason
        }

        return null
    }

    private fun Project.stopAllRunningProcesses() {
        ExecutionManager.getInstance(this).getRunningProcesses().forEach { handler ->
            if (!handler.isProcessTerminated && !handler.isProcessTerminating) {
                handler.destroyProcess()
            }
        }
    }



    private suspend fun openScenarioFiles(
        project: Project,
        scenario: AgentScenario,
    ) {
        val fileEditorManager = FileEditorManager.getInstance(project)

        val projectRoot = project.getProjectDir() ?: error("Failed to get project root")
        val filesToOpen = scenario.openedFiles
            .mapNotNull { projectRoot.resolveFromRootOrRelative(it) }
            .toSet()
            .also { files ->
                require(files.size == scenario.openedFiles.size) {
                    "Couldn't find some of these files to open: ${scenario.openedFiles}"
                }
            }

        withContext (Dispatchers.EDT) {
            fileEditorManager.openFiles
                .filter { it !in filesToOpen }
                .forEach { fileEditorManager.closeFile(it) }

            // Open files in the editor and focus on the last one
            filesToOpen.forEach { file ->
                fileEditorManager.openFile(file, true)
            }
        }
    }

    private suspend fun closeTerminalTabs(project: Project) =
        withContext(Dispatchers.EDT) {
            val terminalManager = TerminalToolWindowManager.getInstance(project)
            ToolWindowManager.getInstance(project)
                .getToolWindow(TerminalToolWindowFactory.TOOL_WINDOW_ID)
                ?.contentManager
                ?.contents
                ?.forEach { content -> terminalManager.detachWidgetAndRemoveContent(content) }
        }

    private fun <T> List<T>.zipWithIndex(): List<IndexedValue<T>> = zip(indices) {
            v, idx -> IndexedValue(idx, v)
    }
}

private fun createRunInfo(
    settings: AgentSettings,
    config: AgentConfig,
    modelName: String
): BenchmarkRunInfo {
    val zoneId = ZoneId.of("Europe/Moscow")
    val dateTimeFormatter = DateTimeFormatter.ofPattern("uuuu-MM-dd'T'HH:mm:ss") // ISO-8601 extended format
    return BenchmarkRunInfo(
        timestamp = LocalDateTime.now(zoneId).format(dateTimeFormatter),
        experimentName = settings.taskName,
        datasetHash = config.defaultRepoHash,
        pluginHash = AgentEnvService.getEnvValue(EnvVariable.PLUGIN_COMMIT_HASH)
            ?: error("`${EnvVariable.PLUGIN_COMMIT_HASH.name}` env variable is not set"),
        datasetConfigHash = getBenchJson().encodeToStringCompatibility(config).getSha256Hash(),
        modelName = modelName, // don't use setting here, cause for enterprise model name is empty
        providerName = settings.providerName,
        modelUrl = settings.modelUrl
    )
}

