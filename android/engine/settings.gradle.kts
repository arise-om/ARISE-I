// The engine is a standalone pure-Kotlin build so it can be developed and
// tested with plain Gradle + a JDK (no Android SDK).  The Android build pulls
// it in with includeBuild("engine").
rootProject.name = "engine"

dependencyResolutionManagement {
    repositories {
        mavenCentral()
    }
}
