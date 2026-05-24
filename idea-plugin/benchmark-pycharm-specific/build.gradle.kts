plugins {
    id("anonymous.pycharm-kotlin-conventions")
}


dependencies {
    implementation(project(":benchmark-common"))
    intellijPlatform {
        bundledPlugins("Git4Idea")
        plugins(provider {
            listOf("PythonCore:${Versions.TargetVersion.pythonCoreVersion}")
        })
    }
}
