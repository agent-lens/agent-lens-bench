
plugins {
    id("anonymous.idea-kotlin-conventions")
}

dependencies {
    implementation(project(":benchmark-common"))

    intellijPlatform {
        plugins(provider {
            listOf("Lombook Plugin:${Versions.TargetVersion.lombokPluginVersion}")
        })

        bundledPlugins("com.intellij.java", "org.jetbrains.kotlin", "Git4Idea", "Coverage", "JUnit",
            "com.intellij.gradle", "org.jetbrains.idea.maven", "org.jetbrains.plugins.terminal")
    }

}
