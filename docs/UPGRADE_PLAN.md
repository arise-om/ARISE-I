# ARISE-I — Audit (v2.1.0) and Upgrade Plan

> Audit date: 2026-10-18 · Baseline: v2.0.0 · Result: v2.1.0 (205 tests: 202 pass, 3 skip on Windows)

---

## 1. Architecture at a glance

```
                    ┌──────────── gui.py (Tk) ────────────┐   CLI: file_organizer.main()
 user ─────────────►│ Organize / Preview / Undo / Review  │◄── arise-i --dry-run|--undo|--watch
                    │ worker threads ──► queue ──► 50 ms   │
                    └───────┬──────────────┬──────────────┘
                            │              │ Auto-Sort
                            ▼              ▼
                  file_organizer.organize_folder ◄── file_watcher (watchdog + debounce)
                            │
   skip_reason() ──► plugins ──► SmartClassifier (classifier.py)
   (own/hidden/system/        ├ L1 extension map   0.92
    partial/lock files)       ├ L2 MIME sniff      0.55–0.92
                              ├ L3 name heuristics 0.76–0.88
                              ├ assignment parser  0.80–0.95 → Subject/Assignment N/Type
                              └ L4 TF-IDF + NB     (model.pkl, optional)
                            │      conf < 0.75 → __Review__/
                            ▼
              move (unique name) ─► .arise-i-log.json (undo manifest) + arise-i.log
                            │
                            └─► LearningStore ─► ~/.arise-i/feedback.jsonl ─► retrain every 50
                                                                  ▲            events / on drift
                     HealthMonitor (60 s thread): manifest repair, disk, Review age, drift
```

| Module | Role | Lines |
|---|---|---|
| `file_organizer.py` | Scan → classify → move, undo, config, CLI | ~1150 |
| `classifier.py` / `assignment_classifier.py` | Multi-layer classifier + assignment parser | ~400 / 145 |
| `learning_store.py` | Feedback log, retrain, model metadata | ~290 |
| `health_monitor.py` | Background self-healing checks | ~300 |
| `file_watcher.py` | watchdog handler, debounce, restart-with-backoff | ~360 |
| `gui.py` / `onboarding.py` / `prefs.py` | Tk dashboard, first-run wizard, prefs | ~1000 / 235 / 80 |
| `plugin_loader.py` | `~/.arise-i/plugins/*.py` → `classify(path)` | ~215 |

**State on disk.** Per target folder: `.arise-i-log.json` (undo history, absolute paths), `arise-i.log`, optional `arise-i.config.yaml`. Global `~/.arise-i/`: `prefs.json`, `feedback.jsonl`, `model.pkl`, `model_meta.json`, `health.json`, `plugins/`.

---

## 2. What the audit found and fixed (v2.1.0)

Each item was reproduced first (probe script or failing test), then fixed and pinned by a regression test. The new tests fail on v2.0.0 (16 failures) and pass on v2.1.0.

| # | Severity | Bug | Evidence |
|---|---|---|---|
| 1 | Critical | **Auto-Sort never fired on new files** — watchdog ≥ 4 sets `dest_path=""` on every event | Real `FileCreatedEvent` ignored; tests used fake events without the attribute |
| 2 | Critical | **In-progress downloads moved** (`.crdownload`, `.part`) → corrupted downloads | Probe |
| 3 | High | **`desktop.ini`, Windows hidden/system files, config file moved** | Probe |
| 4 | High | **Undo overwrote a newer file** at the original path | Probe |
| 5 | High | **Review Queue overwrote** a same-named file; offered only 6 categories | GUI smoke test |
| 6 | High | **Learning loop poisoned**: Review moves logged as `confirmed="__Review__"` | 22 such rows in this machine's `feedback.jsonl` |
| 7 | Medium | Retrained model never loaded in-session; one-class model would claim 100 % | Test |
| 8 | Medium | Health monitor re-ran the same retrain + alerts every 60 s | Probe |
| 9 | Medium | Config in the target folder ignored (README said to put it there) | Probe |
| 10 | Medium | Dark mode: 9 widgets with dark text on dark background | GUI smoke test |
| 11 | Medium | Ctrl+Z undid a run with no confirmation; Tk touched from worker thread | Code review |
| 12 | Medium | Installed builds lost assignment sorting (`assignment_classifier` not packaged) | `SOURCES.txt` |
| 13 | Low | CLI accepted drive root / home; file path as target crashed | Probe |
| 14 | Low | CI lint never ran (unknown `W503` selector hidden by `\|\| true`) | Ran the CI command |
| 15 | Low | Installer version stuck at 1.3.0; README plugin example didn't import | Code review |

Also: plugins + learning now apply to GUI runs, Undo/Preview lock during Auto-Sort, test suite isolated from the real `~/.arise-i`, 12 common extensions added (`.iso`, `.avif`, `.opus`, …), files reorganised into `docs/` and `scripts/`, build artefacts removed.

---

## 3. Known risks still open (deliberately not changed in 2.1)

1. **Undo manifest stores absolute paths** — renaming or moving the organised folder breaks undo.
2. **Moves are not journaled before they happen** — a crash mid-run loses the undo record for that run.
3. **No cross-process lock** — CLI and GUI on the same folder at once can interleave manifest writes.
4. **The model mostly learns from itself** — 918 of 940 local events are the extension layer's own labels; the only real signal is Review corrections. The ML layer currently re-learns the extension map.
5. **`model.pkl` is loaded with `pickle`** — fine inside a single-user home folder, but a poor format to ever sync or share.
6. **Flat top-level modules** (`gui`, `prefs`, `classifier`) are installed straight into `site-packages` and can collide with other packages.
7. **Review resolutions aren't undoable**, and assignment regexes have false positives (`Project 2024 - Budget.xlsx`).
8. **Desktop releases ship without AI extras** (PyInstaller step installs only PyYAML + watchdog).
9. **Owner decision needed**: the classifier says "Production/Stable" but there's no PyPI release yet. (The repo URL mismatch was settled as `arise-om/ARISE-I`.)

### Environment notes (this machine)
- The git repository root is **`C:\`** (one commit, "chore: sync Prompt OS source"); this project isn't tracked by it at all.
- `install.bat` uses the first `python` on `PATH`, which here is the **hermes-agent venv**, so ARISE-I 2.0.0 is installed inside another tool's environment. That copy still has every bug above.
- Drive C: has ~4 GB free (the health monitor recorded 0.4 GB on 2026-10-13).

---

## 4. Next-level plan

### Phase 0 — Ship 2.1 (now, < 1 day)
- `git init` inside the project folder, commit, push, tag `v2.1.0`; let CI run the 3-OS × 3-Python matrix.
- Reinstall into a dedicated venv (`py -3.12 -m venv %LOCALAPPDATA%\ARISE-I\venv`) and make `install.bat` do the same instead of using whatever `python` comes first on `PATH`.

### Phase 1 — Engine foundation (v2.2, 1–2 weeks) ⭐ do this first
The single change that unlocks everything else: **split "decide" from "do".**
- `src/arise_i/` package (`python -m arise_i`, `arise_i.engine`, `arise_i.cli`, `arise_i.gui`) — fixes the module-collision risk.
- `plan(folder) -> list[MoveOp]` is pure and side-effect free; Preview, the GUI table, the CLI and tests all consume it.
- `execute(plan)` writes the journal **before** each move (crash-safe undo), stores paths **relative** to the target, and takes a lock file on the folder.
- A `Run` object owns its logger, so parallel runs can't steal each other's log handlers.
- Review resolutions go through the same executor, so they become undoable too.

### Phase 2 — Intelligence that actually learns (v2.3, 2–3 weeks)
- Train on **corrections, weighted**, not on the classifier's own outputs; keep self-labels only as a capped prior.
- New features with real signal for a Downloads folder: **source URL** (Windows `Zone.Identifier`, macOS `kMDItemWhereFroms`), size bucket, first-page PDF text (`pypdf`), EXIF date/camera.
- Re-classify `__Review__/` automatically after every retrain.
- Replace `pickle` with `skops` (or a JSON-serialised NB); add a confidence-calibration check to `model_meta.json`.
- Opt-in, per-folder models ("Downloads" and "University" sort differently).

### Phase 3 — Product UX (v3.0, 3–4 weeks)
- **System tray + start-on-login background service** (pystray); Auto-Sort survives closing the window.
- **Rule engine** (YAML, editable in the GUI): `name ~ /invoice/ → Documents/Invoices`, `size > 500 MB → LargeFiles`, `source = github.com → Code`.
- **Multi-folder watch** with per-folder rules.
- **Keyboard-first Review Queue** (J/K, Enter, bulk-assign) and a "Plan" table showing every pending move before Organize.
- UI toolkit: keep Tk until Phase 1 lands; then move to **PySide6** if a native look is a priority. The engine split makes this a GUI-only rewrite.

### Phase 4 — Distribution (parallel with Phase 3)
- PyPI via trusted publishing (`pip install arise-i[ai]`).
- **Code-signed** Windows installer (otherwise SmartScreen warns every new user), winget manifest, Homebrew cask, notarised macOS build.
- Ship an "AI" desktop build variant that includes scikit-learn.
- In-app update check against GitHub Releases (opt-in, the only network call).

### Phase 5 — Platform (later)
Local REST API / webhooks, `arise-i find --tag`, NTFS ADS / xattr tagging, team rule sync — as in `PRODUCT_VISION.md` Sprints 5–6.

### Engineering bar for every phase
- Every bug gets a failing test first; keep CI lint blocking.
- Coverage target 85 % for the engine; GUI covered by a headless smoke test (pattern used in this audit: hidden window, isolated `HOME`, pump the event loop).
- Changelog entry and version bump in `pyproject.toml`, `file_organizer.__version__` and the tag. One source of truth for the version is a Phase 1 task.
