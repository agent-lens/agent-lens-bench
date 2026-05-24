import org.jetbrains.intellij.platform.gradle.tasks.RunIdeTask

plugins {
    id("anonymous.pycharm-kotlin-conventions")
}

dependencies {
    implementation(project(":benchmark-common"))
    implementation(project(":benchmark-pycharm-specific"))
    implementation(project(":x-agent-engine"))

    intellijPlatform {
        bundledPlugins("Git4Idea", "org.jetbrains.plugins.terminal")
        plugins(provider {
            listOf("PythonCore:${Versions.TargetVersion.pythonCoreVersion}")
        })

        plugin("com.x.plugin", Versions.xPluginVersion)
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
    description = "Run Python Anonymous Benchmark in Headless Mode"
    dependsOn("runIde")
}
