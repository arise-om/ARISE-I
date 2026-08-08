# ARISE-I — Product Vision & Progress Journal

> **Maintained by:** Om Deshmukh · Ironlabs.tech  
> **Last updated:** 2026-08-08  
> **Current version:** 2.0.0  
> **Status:** Active development → Premium product track

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Project Genesis](#2-project-genesis)
3. [Progress Timeline](#3-progress-timeline)
4. [Current Architecture (v2.0.0)](#4-current-architecture-v200)
5. [Feature Completeness Matrix](#5-feature-completeness-matrix)
6. [Premium Product Roadmap](#6-premium-product-roadmap)
7. [Business Model & Monetization](#7-business-model--monetization)
8. [Competitive Landscape](#8-competitive-landscape)
9. [Technical Debt & Known Issues](#9-technical-debt--known-issues)
10. [Distribution Strategy](#10-distribution-strategy)
11. [Design Language & Brand](#11-design-language--brand)
12. [Engineering Standards](#12-engineering-standards)

---

## 1. Executive Summary

ARISE-I is a **local-first, AI-powered file organization system** built for the desktop. It automatically sorts messy folders (Downloads, Desktop, etc.) into structured category hierarchies using a 4-layer classification engine that learns from user corrections over time.

### Vision

> **"The last file organizer you'll ever need — one that genuinely understands your files and adapts to how you work."**

ARISE-I's goal is to become the **definitive file organization product** for power users, developers, and knowledge workers — combining the simplicity of a one-click tool with the intelligence of a local AI system that respects user privacy.

### North-Star Principles

| Principle | Commitment |
|---|---|
| **Local-first** | Zero cloud, zero data egress, zero API keys — forever |
| **Zero friction** | One click to organize; zero configuration required to start |
| **Transparent AI** | Every decision shows its confidence and reasoning |
| **Self-healing** | The system fixes its own failures without user intervention |
| **Privacy by design** | The model trains on your data, on your machine, only for you |

---

## 2. Project Genesis

### Origin: MARK-I → SmartSort → ARISE-I

| Phase | Tool | Description |
|---|---|---|
| Prototype | **MARK-I** | Basic script: extension-map → move. No GUI, no undo. |
| Iteration 1 | **SmartSort** | Added YAML config, CLI flags, basic deduplication |
| Iteration 2 | **ARISE-I v1.0** | Full packaging (`pyproject.toml`), watchdog daemon, plugin system |
| Iteration 3 | **ARISE-I v1.4** | Tkinter two-panel GUI dashboard, history tab, onboarding wizard |
| Current | **ARISE-I v2.0** | AI classification engine, Review Queue, dark mode, self-healing daemon |

### Key Engineering Pivots

1. **Shebang mismatch fix** (v1.4.1): Discovered pip-generated entry points used system Python instead of venv Python → switched to explicit shell-delegate wrappers in `install.sh`.

2. **AI-first redesign** (v2.0): Replaced the static extension map with a layered confidence-scoring engine. This unlocked the Review Queue and adaptive learning loop.

3. **Self-healing architecture** (v2.0): Added `HealthMonitor` as a background daemon. ARISE-I can now recover from its own failures (manifest corruption, thread crashes, model drift) without the user ever noticing.

---

## 3. Progress Timeline

```
Jul 2026  ████████████████████████████████████████
          ┌─────────────────────────────────────────┐
          │ MARK-I prototype (file mover script)     │
          └─────────────────────────────────────────┘
          ┌─────────────────────────────────────────┐
          │ SmartSort (YAML config, CLI, dedup)      │
          └─────────────────────────────────────────┘
          ┌─────────────────────────────────────────┐
          │ ARISE-I v1.0 (packaging + daemon)        │
          └─────────────────────────────────────────┘

Aug 2026  ████████████████████████████████████████
          ┌─────────────────────────────────────────┐
          │ ARISE-I v1.4 (GUI dashboard + UX)        │
          │  ✓ Two-panel Tkinter layout               │
          │  ✓ History tab + result cards             │
          │  ✓ Onboarding wizard                      │
          │  ✓ Persistent prefs                       │
          └─────────────────────────────────────────┘
          ┌─────────────────────────────────────────┐
          │ ARISE-I v2.0 (AI engine + self-healing)  │
          │  ✓ SmartClassifier (4 layers)             │
          │  ✓ Confidence scoring [HIGH/MED/LOW]      │
          │  ✓ __Review__/ + Review Queue tab         │
          │  ✓ LearningStore (adaptive ML)            │
          │  ✓ HealthMonitor (self-healing daemon)    │
          │  ✓ Dark / Light mode                      │
          │  ✓ Crash-resistant watchdog restart       │
          │  ✓ 120 / 120 tests passing                │
          └─────────────────────────────────────────┘

          ← YOU ARE HERE
```

---

## 4. Current Architecture (v2.0.0)

### Module Map

```
ARISE-I v2.0.0
├── gui.py                   GUI dashboard (Tkinter, dark/light mode)
│   ├── AriseIApp            Main window — 4 tabs, theme engine
│   ├── HealthMonitor hook   Starts/stops background health thread
│   └── LearningStore hook   Feeds corrections from Review Queue
│
├── file_organizer.py        Core orchestrator
│   ├── organize_folder()    Sort loop: scan → classify → move → log
│   ├── SmartClassifier      AI engine (imported from classifier.py)
│   ├── LearningStore        Feedback pipe (imported from learning_store.py)
│   ├── undo_last_run()      Atomic undo from manifest
│   └── Stats                Per-category move counts + sizes
│
├── classifier.py            4-layer AI engine   ← NEW in v2.0
│   ├── Layer 1: ext_map     Extension → category (conf 0.92)
│   ├── Layer 2: MIME sniff  byte-level via filetype / stdlib (conf 0.88)
│   ├── Layer 3: heuristics  Filename regex patterns (conf 0.76–0.88)
│   ├── Layer 4: ML model    sklearn TF-IDF + NaiveBayes (user-trained)
│   └── ClassificationResult {category, confidence, badge, layer, alternatives}
│
├── learning_store.py        Adaptive learning   ← NEW in v2.0
│   ├── record()             Append event to feedback.jsonl
│   ├── retrain()            Train sklearn pipeline from full log
│   └── model_meta()         Human-readable accuracy stats
│
├── health_monitor.py        Self-healing daemon  ← NEW in v2.0
│   ├── _check_manifest()    Auto-repair corrupt JSON logs
│   ├── _check_disk()        Warn on < 500 MB free
│   ├── _check_orphans()     Re-queue Review files older than 7 days
│   └── _check_drift()       High correction rate → auto-retrain
│
├── file_watcher.py          Auto-sort daemon (hardened in v2.0)
│   ├── AriseIEventHandler   Debounced watchdog handler
│   └── watch_folder()       Restart loop with exponential backoff
│
├── plugin_loader.py         Sandboxed plugin system (~/.arise-i/plugins/)
├── prefs.py                 Atomic pref read/write (~/.arise-i/prefs.json)
└── onboarding.py            First-run modal wizard
```

### Data Flow

```
┌──────────────────────────────────────────────────────────┐
│                      User Action                          │
│              (drop file / click Organize Now)             │
└───────────────────────────┬──────────────────────────────┘
                            │
                    organize_folder()
                            │
              ┌─────────────▼────────────┐
              │     SmartClassifier      │
              │                          │
              │  Layer 1: ext_map   0.92 │
              │  Layer 2: MIME      0.88 │
              │  Layer 3: heuristic 0.76 │
              │  Layer 4: ML model  ???? │
              └──────────┬──────────────┘
                         │
              ┌──────────▼──────────┐
              │ confidence ≥ 0.75?  │
              └──┬──────────────────┘
            YES  │    NO
                 │    └──→  __Review__/  ←── Review Queue tab
                 │
           Move to category folder
                 │
           LearningStore.record()
                 │
           (every 50 events)
                 │
           sklearn retrain()
                 │
           classifier.reload_model()
                 │
           🧠  Smarter next time
```

### Storage Layout (`~/.arise-i/`)

```
~/.arise-i/
├── prefs.json          User preferences (last folder, theme, debounce)
├── feedback.jsonl      Append-only classification event log
├── model.pkl           Pickled sklearn pipeline (TF-IDF + NaiveBayes)
├── model_meta.json     Human-readable model stats (accuracy, sample count)
├── health.json         Latest health check results
└── plugins/            User plugins (*.py files)
    └── 01_by_year.py   Example: sort photos by year
```

---

## 5. Feature Completeness Matrix

| Feature | v1.0 | v1.4 | v2.0 | Premium Target |
|---|:---:|:---:|:---:|:---:|
| Extension-based sorting | ✅ | ✅ | ✅ | ✅ |
| YAML custom categories | ✅ | ✅ | ✅ | ✅ |
| CLI (`arise-i --help`) | ✅ | ✅ | ✅ | ✅ |
| Plugin system | ✅ | ✅ | ✅ | ✅ |
| Deduplication (rename) | ✅ | ✅ | ✅ | ✅ |
| Undo support | ✅ | ✅ | ✅ | ✅ |
| Auto-sort daemon | ✅ | ✅ | ✅ | ✅ |
| GUI dashboard | ❌ | ✅ | ✅ | ✅ |
| History tab | ❌ | ✅ | ✅ | ✅ |
| Onboarding wizard | ❌ | ✅ | ✅ | ✅ |
| Persistent prefs | ❌ | ✅ | ✅ | ✅ |
| MIME-type sniffing | ❌ | ❌ | ✅ | ✅ |
| Confidence scoring | ❌ | ❌ | ✅ | ✅ |
| Review Queue tab | ❌ | ❌ | ✅ | ✅ |
| Local ML model (sklearn) | ❌ | ❌ | ✅ | ✅ |
| Adaptive learning loop | ❌ | ❌ | ✅ | ✅ |
| Self-healing daemon | ❌ | ❌ | ✅ | ✅ |
| Dark mode | ❌ | ❌ | ✅ | ✅ |
| Crash-resistant watcher | ❌ | ❌ | ✅ | ✅ |
| System tray icon | ❌ | ❌ | ❌ | 🎯 Sprint 3 |
| Rule-based scheduler | ❌ | ❌ | ❌ | 🎯 Sprint 3 |
| Multi-folder watch | ❌ | ❌ | ❌ | 🎯 Sprint 3 |
| Content-based sort (OCR/NLP) | ❌ | ❌ | ❌ | 🎯 Sprint 4 |
| Folder templates | ❌ | ❌ | ❌ | 🎯 Sprint 4 |
| Auto-tagging | ❌ | ❌ | ❌ | 🎯 Sprint 4 |
| Cross-device sync (local net) | ❌ | ❌ | ❌ | 🎯 Sprint 5 |
| Web dashboard | ❌ | ❌ | ❌ | 🎯 Sprint 5 |
| API / webhook triggers | ❌ | ❌ | ❌ | 🎯 Sprint 5 |

---

## 6. Premium Product Roadmap

### Sprint 3 — Power User UX (2 weeks)

**Goal:** Make ARISE-I feel like a real desktop product, not a developer script.

#### 3.1 System Tray Integration
- Persistent tray icon (pystray) — ARISE-I stays running in background
- Right-click menu: Organize Now / Pause / Open Dashboard / Quit
- Badge counter showing files pending in Review Queue

#### 3.2 Rule Engine
Replace the static extension map with a user-editable rule table:
```
IF filename contains "invoice" → Documents/Invoices/
IF extension in [.py .js .ts] AND path contains "project" → Code/
IF file_size > 500MB → LargeFiles/
IF modified_date < 30 days ago → Archive/
```

#### 3.3 Multi-Folder Watch
- Watch multiple folders simultaneously (Downloads + Desktop + Documents)
- Per-folder rule overrides
- Conflict resolution when the same file matches rules from different folders

#### 3.4 Keyboard-First Review Queue
- `J/K` navigation, `Enter` to confirm, `R` to re-classify
- Bulk select + assign (select 10 screenshots → Images)

---

### Sprint 4 — Deep Intelligence (3 weeks)

**Goal:** Make classification meaningfully smarter than any rule-based tool.

#### 4.1 Content-Based Classification
- **PDF text extraction** (pypdf) — classify by content not just extension
- **Image EXIF** — extract GPS, camera model, date → better photo sorting
- **Office document metadata** — author, title, keywords as features
- **Code language detection** — sort `.py` files by project context

#### 4.2 Deep Learning Layer (Layer 5)
Replace Naive Bayes with a fine-tuned sentence-transformers model:
- Embed filename + path + MIME type as a vector
- Cosine similarity against user's past confirmed classifications
- Cold-start: pre-trained on 50k synthetic filename→category pairs
- Fine-tuning: continues locally from user feedback
- **Model size target:** < 50 MB quantized ONNX

#### 4.3 Smart Folder Templates
- "Student laptop" template: Assignments, Lectures, Research, Exams
- "Developer" template: Projects, Screenshots, Docs, Installers
- "Creative" template: References, Exports, Drafts, Assets
- User can save/share their own templates

#### 4.4 Auto-Tagging
- Tag files with metadata labels without moving them
- Platform-native tags: extended attributes on Linux/macOS, NTFS ADS on Windows
- Search `arise-i find --tag invoice --after 2026-01`

---

### Sprint 5 — Platform & Distribution (2 weeks)

**Goal:** Ship as a polished, distributable product to real users.

#### 5.1 Distribution
- **PyPI**: `pip install arise-i` (base), `pip install arise-i[ai]` (with ML)
- **GitHub Releases**: Standalone executables for Linux / macOS / Windows (CI already built)
- **Homebrew Cask**: `brew install --cask arise-i`
- **Snap / Flatpak**: For Linux desktop users who don't use pip

#### 5.2 Web Dashboard (optional, local)
- FastAPI server running at `localhost:7474`
- React-based dashboard for managing categories, reviewing files, viewing stats
- Accessible remotely on local network → enables NAS/server deployments

#### 5.3 API & Automation
```bash
# Webhooks for custom integrations
arise-i webhook add --on file_sorted --url http://localhost:5000/callback
arise-i api serve --port 7474

# Example REST call
curl -X POST localhost:7474/organize -d '{"path": "~/Downloads"}'
```

#### 5.4 Premium "Pro" Features (if monetizing)
| Free | Pro ($5/mo or $49/yr) |
|---|---|
| 1 watched folder | Unlimited folders |
| Extension + MIME + heuristics | + ML model + content analysis |
| Basic Review Queue | Priority queue + batch actions |
| Light theme only | Light + Dark + Custom |
| Community support | Email support |

---

### Sprint 6 — Enterprise & Teams (future)

- **Team config sync** (git-backed category rules shared across a team)
- **Audit log** (who sorted what, when — for compliance)
- **NAS mode** (headless, serve dashboard over local network)
- **Active Directory / LDAP** integration

---

## 7. Business Model & Monetization

### Option A — Open Core (Recommended)

```
┌────────────────────────────────────────────┐
│  ARISE-I Free (MIT License)                │
│  – All v2.0 features                       │
│  – Local ML model                          │
│  – 1 watched folder                        │
└────────────────────────────────────────────┘
               ↓ upgrade path ↓
┌────────────────────────────────────────────┐
│  ARISE-I Pro ($49/year)                    │
│  – Unlimited folders                       │
│  – Content-based classification (OCR/NLP)  │
│  – Rule engine                             │
│  – Web dashboard                           │
│  – Priority support                        │
└────────────────────────────────────────────┘
               ↓ upgrade path ↓
┌────────────────────────────────────────────┐
│  ARISE-I Teams ($9/user/month)             │
│  – Shared category templates               │
│  – Audit log                               │
│  – Admin dashboard                         │
└────────────────────────────────────────────┘
```

### Option B — One-Time Purchase

- **$29** standalone license (perpetual, one machine)
- Updates for 1 year; pay $15 for future major versions
- Aligns well with the desktop app market (similar to Raycast, CleanMyMac, etc.)

### Option C — SaaS with local processing

- Subscription for cloud sync of rules/templates and web dashboard
- All actual file processing remains 100 % local (key privacy differentiator)
- $8/month — similar to 1Password / Obsidian Sync pricing model

### Recommended Path

Start with **Option A (Open Core)**:
1. Launch free tier on GitHub and ProductHunt
2. Build reputation and user base
3. Introduce Pro features once community is established
4. Enterprise tier when there are team inquiries

---

## 8. Competitive Landscape

| Product | Platform | AI? | Local? | Price | ARISE-I Advantage |
|---|---|---|---|---|---|
| **Hazel** | macOS only | Rules-based | ✅ | $42 one-time | Cross-platform + ML |
| **File Juggler** | Windows only | Rules-based | ✅ | €29 | Cross-platform + AI |
| **Organize** (iOS/macOS) | Apple only | ❌ | ✅ | $9.99 | Linux + ML learning |
| **Zapier / n8n** | Cloud | ❌ | ❌ | $20+/mo | Privacy, offline |
| **Built-in OS tools** | Platform-native | ❌ | ✅ | Free | Smarter, visual |

### ARISE-I Differentiators

1. **Cross-platform** — Works identically on Linux, macOS, Windows
2. **True local AI** — Not "AI" in marketing name only; actual sklearn model that improves
3. **Confidence transparency** — Users see why every decision was made
4. **Privacy guarantee** — Verifiable: inspect the source code
5. **Developer-extensible** — Plugin system, YAML config, CLI API
6. **Self-healing** — No stale daemons, no silent failures

---

## 9. Technical Debt & Known Issues

### High Priority

| Issue | Impact | Fix Plan |
|---|---|---|
| `_refresh_theme_colors()` only updates bg on most widgets — colors not fully theme-aware after toggle | Visual inconsistency on theme switch | Sprint 3: rebuild UI with a proper style registry (dict of widget refs → re-apply on toggle) |
| `learning_store.retrain()` runs on the health monitor thread — blocks other checks for up to 5s | Health checks delayed during retrain | Sprint 3: run retrain in its own `concurrent.futures.ThreadPoolExecutor` |
| No test for `classifier.py`, `learning_store.py`, `health_monitor.py` | Regression risk | Sprint 3: write unit tests for all v2.0 modules |
| `__Review__/` files not re-classified automatically when model improves | Files may sit in Review forever | Sprint 4: add scheduler that re-attempts Review folder after every model retrain |

### Medium Priority

| Issue | Fix Plan |
|---|---|
| GUI sort worker passes `learning_store=None` on dry runs — correct, but should log that feedback is disabled | Add debug log line |
| `_build_review_card()` shows top-6 categories alphabetically, not ranked by classifier confidence | Use `SmartClassifier.classify().alternatives` to rank suggestions |
| Manifest `moves` entries now include `confidence` and `layer` but undo logic ignores them | Future: "undo only moves below X% confidence" |
| `install.sh` doesn't update an existing installation correctly (re-creates venv from scratch) | Sprint 3: add `--upgrade` flag to installer |

### Low Priority

| Issue | Fix Plan |
|---|---|
| `_font()` hardcodes Ubuntu — not all Linux users have Ubuntu font installed | Fallback chain: Ubuntu → DejaVu Sans → TkDefaultFont |
| `health.json` grows unbounded (each check overwrites, not appends) | Already correct — it's a single-object overwrite, not accumulation |

---

## 10. Distribution Strategy

### Immediate (This Week)

- [ ] Write `CHANGELOG.md` (done — see file)
- [ ] Commit all v2.0 changes and tag `v2.0.0`
- [ ] Update GitHub release notes
- [ ] Add CI test workflow (`.github/workflows/test.yml`) — done

### Short-Term (Sprint 3)

- [ ] Publish to **PyPI** (`python -m build && twine upload`)
  - `pip install arise-i` → base
  - `pip install arise-i[ai]` → full AI
- [ ] Submit to **Awesome Python** list
- [ ] Post to **r/Python**, **r/linux**, **HackerNews** Show HN
- [ ] Create a 60-second demo GIF for the README

### Medium-Term (Sprint 4–5)

- [ ] **ProductHunt launch** (coordinate with existing users for upvotes)
- [ ] **Homebrew Cask** submission
- [ ] **Flatpak** packaging (Linux desktop discovery)
- [ ] Blog post: "How I built a self-healing AI file organizer in Python"

### Long-Term

- [ ] **Windows Store** (via MSIX packaging)
- [ ] **App Store** (macOS, if we build a proper sandboxed app)

---

## 11. Design Language & Brand

### Color System

| Token | Light | Dark | Usage |
|---|---|---|---|
| `BG` | `#f5f5f7` | `#1c1c1e` | Root background |
| `SURFACE` | `#ffffff` | `#2c2c2e` | Cards, panels |
| `ACCENT` | `#007AFF` | `#0A84FF` | Primary CTA, active tab |
| `GREEN` | `#34C759` | `#30D158` | Success, HIGH confidence |
| `YELLOW` | `#FFD60A` | `#FFD60A` | Warning, MED/LOW confidence |
| `RED` | `#FF3B30` | `#FF453A` | Error |
| `FG` | `#1d1d1f` | `#f2f2f7` | Primary text |
| `FG_DIM` | `#86868b` | `#8e8e93` | Secondary text, labels |

> **Inspired by:** Apple Human Interface Guidelines (macOS) — clean, generous whitespace, semantic color.

### Typography

- **Linux:** Ubuntu (fallback: DejaVu Sans, TkDefaultFont)
- **macOS:** SF Pro Display
- **Windows:** Segoe UI

### Naming Convention

- **ARISE-I**: The full product name (always hyphenated, capitalized)
- **arise-i**: The CLI command and PyPI package name
- **ARISE-I Pro / Teams**: Future tier names

---

## 12. Engineering Standards

### Code Quality

```
Tests:    pytest tests/ -v             → target: 100% pass, >80% coverage
Types:    All public functions typed    → enforce with mypy in CI
Docs:     All public APIs docstrung    → enforce in code review
Style:    ruff / flake8                → add to CI (Sprint 3)
```

### Release Process

```
1. Bump version in pyproject.toml
2. Update CHANGELOG.md
3. Run full test suite (120+ tests)
4. git tag v{major}.{minor}.{patch}
5. git push origin main --tags
6. GitHub Actions builds standalone apps (existing CI)
7. python -m build && twine upload (PyPI — Sprint 5)
```

### Branch Strategy

```
main          ← stable, tagged releases only
dev           ← integration branch for features
feature/*     ← individual feature branches
hotfix/*      ← critical bug fixes cherry-picked to main
```

### Commit Conventions (Conventional Commits)

```
feat: add system tray icon
fix: repair manifest corruption on Windows paths
docs: update README for v2.0 AI features
test: add classifier unit tests
refactor: extract theme engine into ThemeManager class
chore: bump scikit-learn to 1.5
```

---

## Appendix: Session Log

| Date | Session | What Was Built |
|---|---|---|
| Jul 2026 | MARK-I origin | Basic file mover script |
| Jul 2026 | SmartSort | YAML config, CLI, dedup |
| Jul 31 2026 | ARISE-I audit | Full v1.4.0 GUI overhaul (two-panel dashboard, history, onboarding) |
| Aug 8 2026 | v2.0 Sprint 1 | Debugged install.sh shebang mismatch; established v2.0 architecture plan |
| Aug 8 2026 | v2.0 Sprint 2 | Implemented: `classifier.py`, `learning_store.py`, `health_monitor.py`; wired into `file_organizer.py`, `file_watcher.py`, `gui.py`; dark mode; Review Queue tab; 120 tests passing |
| Aug 8 2026 | Completion | `install.sh` AI prompt, `requirements.txt`, `CHANGELOG.md`, `CONTRIBUTING.md`, CI test workflow, `PRODUCT_VISION.md` |

---

*ARISE-I is built by Om Deshmukh at [Ironlabs.tech](https://ironlabs.tech)*  
*"Autonomous, Resilient, Intelligent System — Edition I"*
