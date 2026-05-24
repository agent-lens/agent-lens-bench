package com.anonymous.benchmark.common.dialogs

import com.anonymous.benchmark.common.utils.afterNonEqChange
import com.intellij.openapi.fileChooser.FileChooserDescriptor
import com.intellij.openapi.observable.properties.AtomicProperty
import com.intellij.openapi.ui.DialogWrapper
import com.intellij.ui.dsl.builder.AlignX
import com.intellij.ui.dsl.builder.bindSelected
import com.intellij.ui.dsl.builder.bindText
import com.intellij.ui.dsl.builder.panel
import com.intellij.ui.dsl.builder.selected
import com.intellij.util.ui.JBUI
import java.nio.file.Paths
import javax.swing.JComponent
import kotlin.io.path.exists

class AgentSettingsDialog(previousSettings: AgentSettings? = null) : DialogWrapper(null) {
    private val taskName = AtomicProperty(previousSettings?.taskName ?: "")
    private val chosenConfigPath = AtomicProperty(previousSettings?.configFilePath ?: "")
    private val chosenDirectoryToSaveDumpsPath = AtomicProperty(previousSettings?.whereToSaveDumpsDirectory ?: "").apply {
        afterNonEqChange { isOKActionEnabled = Paths.get(it).exists() }
    }
    private var clearDirectory = previousSettings?.clearFolder ?: false

    private var useAllUsers: Boolean = previousSettings?.useAllUsers ?: true
    private var projectsRootPath: String = previousSettings?.projectsRootPath ?: ""
    private var providerName: String = "OpenAI"
    private var modelName: String = "gpt-5-mini"
    private var modelUrl: String = ""

    fun getAgentSettings(): AgentSettings {
        return AgentSettings(
            taskName.get(),
            chosenConfigPath.get(),
            chosenDirectoryToSaveDumpsPath.get(),
            clearDirectory,
            useAllUsers,
            projectsRootPath,
            providerName,
            modelName,
            modelUrl
        )
    }

    @Suppress("UnstableApiUsage")
    override fun createCenterPanel(): JComponent {
        return panel {
            row {
                textField()
                    .align(AlignX.FILL)
                    .bindText(taskName)
                    .comment(SPECIFY_TASK_NAME)
            }

            row {
                val descriptor = FileChooserDescriptor(
                    false,
                    true,
                    false,
                    false,
                    false,
                    false
                ).withTitle(CHOOSE_WHERE_TO_STORE_JSONS)

                textFieldWithBrowseButton(fileChooserDescriptor = descriptor, project = null) { file ->
                    file.path
                }.align(AlignX.FILL)
                    .bindText(chosenDirectoryToSaveDumpsPath)
                    .comment(CHOOSE_WHERE_TO_STORE_JSONS)
            }

            row {
                val descriptor = FileChooserDescriptor(
                    true,
                    false,
                    false,
                    false,
                    false,
                    false
                ).withTitle(CHOOSE_CONFIG_FILE)

                textFieldWithBrowseButton(fileChooserDescriptor = descriptor, project = null) { file ->
                    file.path
                }.align(AlignX.FILL)
                    .bindText(chosenConfigPath)
                    .comment(CHOOSE_CONFIG_FILE)
            }
            row {
                checkBox("Clear directory").bindSelected(::clearDirectory)
            }


            row {
                checkBox("Use all users").bindSelected(::useAllUsers).selected(true)
            }
            separator()

            row {
                val descriptor = FileChooserDescriptor(
                    false,
                    true,
                    false,
                    false,
                    false,
                    false
                ).withTitle("")

                textFieldWithBrowseButton(fileChooserDescriptor = descriptor, project = null) { file ->
                    file.path
                }.align(AlignX.FILL)
                    .bindText(::projectsRootPath)
                    .comment("Benchmark dataset path")
            }
            row {
                textField()
                    .align(AlignX.FILL)
                    .bindText(::providerName)
                    .comment("Provider name")
            }
            row {
                textField()
                    .align(AlignX.FILL)
                    .bindText(::modelName)
                    .comment("Model name")
            }
            row {
                textField()
                    .align(AlignX.FILL)
                    .bindText(::modelUrl)
                    .comment("Model url (optional)")
            }

        }
    }

    init {
        title = "Benchmark Run Settings"
        super.init()
        isOKActionEnabled = false
        setSize(INITIAL_DIALOG_WIDTH, INITIAL_DIALOG_HEIGHT)
    }

    companion object {
        private const val CHOOSE_WHERE_TO_STORE_JSONS = "Choose Where to Store Jsons"
        private const val SPECIFY_TASK_NAME = "Specify Task Name"
        private const val CHOOSE_CONFIG_FILE = "Choose Config File (or default will be used)"


        private val INITIAL_DIALOG_WIDTH = JBUI.scale(400)
        private val INITIAL_DIALOG_HEIGHT = JBUI.scale(200)
    }
}

data class ModelSettings(
    val providerName: String,
    val modelName: String,
    val modelUrl: String? = null,
)

data class AgentSettings(
    val taskName: String,
    val configFilePath: String?,
    val whereToSaveDumpsDirectory: String,
    val clearFolder: Boolean,
    val useAllUsers: Boolean,
    val projectsRootPath: String,
    val providerName: String,
    val modelName: String,
    val modelUrl: String? = null,
    val agentEngineUrl: String? = null
) {

    fun getModelSettings(): ModelSettings =
        ModelSettings(
            providerName,
            modelName,
            modelUrl,
        )
}
