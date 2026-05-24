import org.jetbrains.intellij.platform.gradle.tasks.RunIdeTask

plugins {
    id("agent.lens.idea-kotlin-conventions")
}

dependencies {
    implementation(project(":benchmark-common"))
    implementation(project(":benchmark-idea-specific"))
    implementation(project(":explyt-agent-engine"))

    intellijPlatform {
        plugins(provider {
            listOf("Lombook Plugin:${Versions.TargetVersion.lombokPluginVersion}")
        })

        bundledPlugins("org.jetbrains.plugins.terminal", "Git4Idea")
        plugin("com.explyt.test", Versions.explytPluginVersion)
    }

}


gradle.taskGraph.whenReady {
    if (hasTask("${project.path}:runHeadless")) {
        tasks.named<RunIdeTask>("runIde").configure {
            val sandboxLogFolder = sandboxLogDirectory.asFile.get().absolutePath
            jvmArgs(
                listOf(
                    "-Djava.awt.headless=true",
                    "-Dagent.bench.run=true",
                    "-XX:+HeapDumpOnOutOfMemoryError",
                    "-XX:HeapDumpPath=${sandboxLogFolder}",
                    "-XX:ErrorFile=${sandboxLogFolder}/hs_err_pid%p.log",
                    "-XX:+ExitOnOutOfMemoryError",
                    "-Xmx4096m",
                )
            )
        }
    }
}

tasks.register("runHeadless") {
    group = "intellij platform"
    description = "Run Idea AgentLens Benchmark in Headless Mode"
    dependsOn("runIde")
}
