
plugins {
    id("agent.lens.idea-kotlin-conventions")
}

dependencies {
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:${Versions.kotlinxSerializationVersion}")
    implementation(project(":benchmark-common"))

    intellijPlatform {
        bundledPlugins("org.jetbrains.plugins.terminal", "Git4Idea")
        plugin("com.x.plugin", Versions.xPluginVersion)
    }
}
