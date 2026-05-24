plugins {
    id("anonymous.idea-kotlin-conventions")
}

dependencies {
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:${Versions.kotlinxSerializationVersion}")
    compileOnly("org.springframework.ai:spring-ai-openai:${Versions.springAiVersion}")

    intellijPlatform {
        bundledPlugins("org.jetbrains.plugins.terminal", "Git4Idea")
    }
}
