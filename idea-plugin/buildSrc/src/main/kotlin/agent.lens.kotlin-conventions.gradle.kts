import org.gradle.kotlin.dsl.withType
import org.jetbrains.intellij.platform.gradle.CustomPluginRepositoryType
import org.jetbrains.kotlin.gradle.dsl.JvmTarget
import org.jetbrains.kotlin.gradle.tasks.KotlinCompile
import java.net.URI

plugins {
    id("org.jetbrains.kotlin.jvm")
    kotlin("plugin.serialization")
    id("maven-publish")
    id("org.jetbrains.intellij.platform.module")
    id("org.jetbrains.intellij.platform")
}

repositories {
    maven { url = uri("https://repo1.maven.org/maven2/") }
    mavenLocal()
    intellijPlatform {
        defaultRepositories()
        snapshots()
        localPlatformArtifacts()
    }
}

private val publishedProjects = setOf(
    ":benchmark-common",
    ":benchmark-idea-specific",
    ":benchmark-pycharm-specific",
)

if (project.path in publishedProjects) {
    publishing {
        repositories {
            maven {
                name = "GitHubPackages"
                url = URI("https://maven.pkg.github.com/agent-lens/agent-lens-bench")
                credentials { configurePublishingCredentials() }
            }
        }
    }

    publishing {
        publications {
            create<MavenPublication>("mavenJava") {
                from(components["java"])
            }
        }
    }
}

private fun PasswordCredentials.configurePublishingCredentials() {
    username = System.getenv("GITHUB_ACTOR")
    password = System.getenv("GITHUB_TOKEN")
}

group = "com.agentlens.benchmark"
version = System.getenv("BENCHMARK_VERSION") ?: "0.1-local"

configurations.all {
    // needed for IntelliJ IDEA 2024.3+
    // we should let compiler itself use stuff like kotlinx-serialization
    if (name.contains("Compiler") || name.contains("kotlinBuildToolsApi")) {
        return@all
    }

    exclude(group = "org.jetbrains.kotlinx", module = "kotlinx-serialization-core")
    exclude(group = "org.jetbrains.kotlinx", module = "kotlinx-serialization-core-jvm")
    exclude(group = "org.jetbrains.kotlinx", module = "kotlinx-serialization-json")

    exclude(group = "com.fasterxml.jackson.core", module = "jackson-core")
    exclude(group = "com.fasterxml.jackson.core", module = "jackson-annotations")
    exclude(group = "com.fasterxml.jackson.core", module = "jackson-databind")
    exclude(group = "com.fasterxml.jackson.module", module = "jackson-module-kotlin")

    // more details about logging in Intellij: https://blog.jetbrains.com/platform/2022/02/removing-log4j-from-the-intellij-platform/
    exclude(group = "org.slf4j", module = "slf4j-api")
    exclude(group = "org.slf4j", module = "slf4j-simple")
    exclude(group = "org.apache.logging.log4j", module = "log4j-slf4j2-impl")
}

dependencies {
    implementation("io.github.microutils:kotlin-logging:${Versions.kotlinLoggingVersion}")
}

intellijPlatform {
    buildSearchableOptions = false
}

tasks {

    withType<KotlinCompile>().configureEach {
        compilerOptions {
            jvmTarget.set(JvmTarget.JVM_21)
        }
    }

    withType<JavaCompile> {
        options.encoding = "UTF-8"
        options.compilerArgs = options.compilerArgs + "-Xlint:all"
        sourceCompatibility = JavaVersion.VERSION_21.toString()
        targetCompatibility = JavaVersion.VERSION_21.toString()
    }

    withType<KotlinCompile>().configureEach {
        compilerOptions {
            freeCompilerArgs.addAll(
                listOf(
                    "-Xallow-result-return-type",
                    "-Xsam-conversions=class",
                    "-Xcontext-parameters",
                    "-opt-in=org.jetbrains.kotlin.K1Deprecation"
                )
            )
            languageVersion.set(org.jetbrains.kotlin.gradle.dsl.KotlinVersion.KOTLIN_2_0)
            apiVersion.set(org.jetbrains.kotlin.gradle.dsl.KotlinVersion.KOTLIN_2_0)
        }
    }
}
