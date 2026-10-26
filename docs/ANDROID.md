# ARISE-I for Android

A native Kotlin + Jetpack Compose port of ARISE-I. It sorts files with the same rules as the desktop app, and everything stays on the phone. The app has **no INTERNET permission**, and CI fails the build if one ever appears.

- **Install:** download `ARISE-I-Android.apk` from a GitHub release and open it. You may need to allow "Install unknown apps" for your browser or file manager.
- **Requirements:** Android 8.0 (API 26) or newer.

---

## What it does

| | |
|---|---|
| **Organize** | Tap **Organize…** to open the **Plan**: every file grouped by destination folder, each with a confidence chip. Untick a file to leave it alone, or tap it to send it somewhere else. Nothing moves until you tap **Organize N files**. **Stop** is always safe. |
| **Review** | Files ARISE-I isn't sure about go to `__Review__/`, never into the wrong folder. Swipe right to accept the best guess, swipe left for "Not now" (comes back in a week), or long-press to select several. Every choice teaches the classifier, and every choice can be undone. |
| **Undo** | From History you can undo a whole run or a single file. Undo never overwrites anything: a file that took the original name since keeps it, and the restored file gets " (1)". If you moved the folder, use **Locate it** to point the run at its new location. |
| **Auto-sort** | Each folder can be set to **Off**, **Every 15 minutes** (WorkManager, easy on battery) or **Instantly**. Instantly uses a FileObserver in a foreground service and shows a small ongoing notification. Auto-sort only moves a file once it has stopped changing. Result notifications have **Undo** and **Review** buttons, and the Quick Settings tile pauses or resumes every folder. |
| **Health** | Every 6 hours the app finishes any interrupted run, warns about low storage and files waiting more than a week, and retrains the model when the correction rate climbs. |
| **Custom categories** | Put an `arise-i.config.yaml` in the folder. The format is the same as on desktop. |

Not on Android: the desktop's Python plugins (`~/.arise-i/plugins`).

---

## Architecture

```
android/
├── engine/   pure Kotlin/JVM, no Android imports — standalone Gradle build
│   ├── Rules.kt            loads arise-rules.json (exported from Python)
│   ├── Classifier.kt       extension → magic-byte MIME → heuristics → assignments → Naive Bayes
│   ├── Organizer.kt        plan / execute / undo / Review moves / crash recovery
│   ├── MoveJournal.kt      append-only write-ahead journal (journal.jsonl)
│   ├── LearningStore.kt    feedback log with retraction + model.json
│   └── HealthChecker.kt    port of health_monitor.py
└── app/      Compose UI, WorkManager, FileObserver service, notifications, QS tile
```

### One set of rules for both apps
`scripts/export_rules.py` writes the Python classifier tables to `android/engine/src/main/resources/arise-rules.json`. CI runs it with `--check`, so a rule change that skips the export fails.

`tests/fixtures/classification_golden.json` lists 49 tricky file names and where a run must leave each one. Both engines must pass it:
- Python: `tests/test_golden.py`
- Kotlin: `ClassifierParityTest`

### Crash safety
Every run is first written to the journal: all planned moves, fsynced, before any file is touched. Each move is then marked in flight and done.

If the process dies, recovery checks every unfinished move against what is actually on disk. Recovery runs at start-up, before every run, and in the health check:

| What's on disk | Recovery |
|---|---|
| Only the destination exists | Marked moved |
| Only the source exists | Marked skipped |
| Both exist (the copy fallback was cut short) | The copy is dropped and the source kept |

`CrashSafetyTest` kills the run before every single disk operation. It covers the rename and copy paths, for both runs and undos, and asserts that no file is lost or duplicated, no temp copy is left behind, and everything can still be undone.

---

## Building

The engine needs only a JDK:

```bash
android/gradlew -p android/engine test
```

The app needs JDK 17 and the Android SDK (platform 35):

```bash
cd android
./gradlew :app:assembleDebug        # app/build/outputs/apk/debug/
./gradlew :app:lintDebug
```

After changing any classifier table in Python:

```bash
python scripts/export_rules.py
```

Behaviour that lives in code rather than tables has a hand-written Kotlin port
and must be changed in both places: copy-suffix stripping in
`arise_i/core/assignment.py` ↔ `AssignmentParser.kt`, folder-name sanitising
in `arise_i/core/paths.py` ↔ `FileNames.kt`, and Review/assignment placement
in `arise_i/core/organizer.py` ↔ `Organizer.kt`. Add a golden case for any such
change so the parity tests catch a missed port.

### Release signing
`release.yml` builds `ARISE-I-Android.apk` on every `v*` tag. To sign it with your own key, add these repository secrets:

| Secret | Value |
|---|---|
| `ANDROID_KEYSTORE_B64` | `base64 -w0 release.jks` |
| `ANDROID_STORE_PASSWORD` | keystore password |
| `ANDROID_KEY_ALIAS` | key alias |
| `ANDROID_KEY_PASSWORD` | key password |

Without them the APK is signed with the debug key. It still installs, but you can't update it in place with a properly signed build later.

---

## Manual test checklist
1. Install the APK. Onboarding should ask for All files access, then show Downloads with its loose-file count.
2. Push demo files to the phone:
   ```bash
   python scripts/create_demo_files.py
   adb push <demo>/. /sdcard/Download/
   ```
3. **Show me the plan:**
   - untick one file and re-route another;
   - tap **Organize**, then check the folders in Files and that Gallery shows the moved photos;
   - in History, undo one file, then the whole run.
4. Set Downloads to **Instantly** and `adb push` a new file. It should be sorted within a few seconds, and the notification should offer Undo.
5. A file like `mystery.bin` goes to Review. Swipe it right, then tap Undo on the snackbar.
6. Start a large run and kill the app with `adb shell am kill tech.ironlabs.arisei`. On reopening, the "We tidied up an interrupted run" card should appear and every file should be present.
7. Check TalkBack, 200 % font size, dark mode and Settings → Reduce motion.
