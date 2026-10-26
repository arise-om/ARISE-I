# kotlinx.serialization: keep generated serializers for the engine's journal,
# feedback log, model and rules (loaded reflectively by companion lookup).
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.**
-keepclassmembers class tech.ironlabs.arisei.** {
    *** Companion;
}
-keepclasseswithmembers class tech.ironlabs.arisei.** {
    kotlinx.serialization.KSerializer serializer(...);
}
-keep,includedescriptorclasses class tech.ironlabs.arisei.**$$serializer { *; }

# SnakeYAML Engine references java.beans, which Android does not ship.
-dontwarn java.beans.**
