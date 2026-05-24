import org.gradle.kotlin.dsl.dependencies

plugins {
    id("anonymous.kotlin-conventions")
}

dependencies {
    intellijPlatform {
        create(Versions.TargetVersion.pycharmIdeType, Versions.TargetVersion.intellijVersion)
    }
}
