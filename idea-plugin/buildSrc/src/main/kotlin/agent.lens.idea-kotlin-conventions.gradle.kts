import org.gradle.kotlin.dsl.dependencies

plugins {
    id("agent.lens.kotlin-conventions")
}

dependencies {
    intellijPlatform {
        create(Versions.TargetVersion.ideaIdeType, Versions.TargetVersion.intellijVersion)
    }
}
