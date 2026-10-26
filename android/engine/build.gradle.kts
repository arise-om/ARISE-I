import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    kotlin("jvm") version "2.0.21"
    kotlin("plugin.serialization") version "2.0.21"
    `java-library`
}

group = "tech.ironlabs.arisei"
version = "2.1.0"

java {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}

kotlin {
    compilerOptions { jvmTarget.set(JvmTarget.JVM_17) }
}

dependencies {
    api("org.jetbrains.kotlinx:kotlinx-serialization-json:1.7.3")
    implementation("org.snakeyaml:snakeyaml-engine:2.8")

    testImplementation(kotlin("test"))
    testImplementation("org.junit.jupiter:junit-jupiter:5.11.3")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}

tasks.test {
    useJUnitPlatform()
    // Non-ASCII file names need a UTF-8 file-name encoding (always true on Android).
    environment("LC_ALL", "C.UTF-8")
    // Shared with tests/test_golden.py so both engines are held to one fixture.
    systemProperty(
        "arise.golden",
        rootDir.resolve("../../tests/fixtures/classification_golden.json").canonicalPath,
    )
}
