# 🤖 Jarvis: Your Local AI Assistant  
*Version: v0.1-planning-complete*

A modular, privacy-respecting, performance-optimized personal AI assistant built for creators, coders, students, and lifelong learners. Designed to evolve with your interests — from Obsidian notes to dev projects, voice control, automation, calendar integration, and more.

---

## ✅ Features

### 🧠 Core Intelligence
- Local LLM Assistant (modular + swappable models) **[✔️ Full: modular, swappable, multi-model integration, profile/fallback ready]**
- Context-aware note generation (Zettelkasten atomic notes) **[✔️ Full: context_note.py, context-aware, vault-aware]**
- Style-aware summarization & cleaning **[✔️ Full: summarize.py, polish.py, note_polish.py, modular, profile-aware]**
- Intelligent note splitting & backlinking **[✔️ Full: smart_link.py, LLM-powered, context-aware, atomic splitting, extensible]**
- Memory of structure, writing style, preferences **[✔️ Full: memory.py, persistent, assistant_context.json]**
- Assistant memory for tasks, files, projects, and features **[✔️ Full: memory.py, persistent, task_log.json]**
- Auto prompt optimization and routing to the right model **[✔️ Full: automatic, context-aware, model_router.py, no manual selection needed]**

---

### 📂 Obsidian Integration
- Clean up, polish, and split notes intelligently **[✔️ Full: polish.py, note_polish.py, modular, profile-aware]**
- Summarize notes **[✔️ Full: summarize.py, modular, profile-aware, dynamic timeout, large input support]**
- Auto metadata tagging and backlinking **[✔️ Full: smart_link.py, extensible, context-aware]**
- Note structure matching existing vault style **[✔️ Full: context_note.py, vault-aware]**
- Zettelkasten-style unique ID generation **[✔️ Full: context_note.py]**
- Vault-wide content suggestions (semantic linking) **[✔️ Full: smart_link.py, context-aware]**
- Daily/weekly refactor schedules **[✔️ Full: refactor.py, memory/refactor_schedule.json, CLI: refactor-schedule, refactor-jobs, refactor-remove, refactor-scheduler]**
- Git-based vault backup & auto push **[✔️ Full: backup.py, CLI command, PAT/SSH, modular]**
- Embed vector search (via local embeddings) **[Planned]**

---

### 🧠 Persistent Memory System
- `memory/` folder for:
  - Assistant behavior, preferences, history **[✔️ Full: memory.py, assistant_context.json, prefs.json, CLI: prefs, history]**
  - Feature learning (self-modifying feature registry) **[✔️ Full: memory.py, feature_registry.json, CLI: feature_registry, remember, forget]**
  - Task logs and frequent workflows **[✔️ Full: memory.py, task_log.json, CLI: task_log, frequent]**
- Natural-language feature learning (e.g., “Jarvis, always summarize EOD”) **[✔️ Full: memory.py, CLI: remember, forget]**
- CLI commands: `prefs`, `history`, `feature_registry`, `task_log`, `frequent`, `remember`, `forget` **[✔️ Full]**

---

### 🌟 Interest/Topic Enhancement Features
- Interest/topic visualization (word cloud, bar chart) **[✔️ Full: interest_features.py, now in main CLI]**
- Change tracking (snapshots of interests over time) **[✔️ Full: interest_features.py, now in main CLI]**
- Interest-to-note mapping (see which notes mention each topic) **[✔️ Full: interest_features.py, now in main CLI]**
- Grouping/clustering of similar interests (string similarity) **[✔️ Full: interest_features.py, now in main CLI]**
- Export/sharing of interests and mappings (JSON, CSV) **[✔️ Full: interest_features.py, now in main CLI]**
- Note recommendations for each interest (longest/most relevant) **[✔️ Full: interest_features.py, now in main CLI]**
- Automated tagging of notes with detected interests **[✔️ Full: interest_features.py, now in main CLI]**
- Interest-driven summaries (summarize all notes about a topic) **[✔️ Full: interest_features.py, now in main CLI]**
- Reminders/tasks for stale interests (not updated recently) **[✔️ Full: interest_features.py, now in main CLI]**
- Similarity search for interests/topics **[✔️ Full: interest_features.py, now in main CLI]**

---

### 🧠 Assistant Memory & Feature Learning Enhancements
- User action, preference, and history logging **[✔️ Full: assistant_memory_features.py, now in main CLI]**
- Feature learning (self-modifying feature registry, enables/disables features based on usage) **[✔️ Full: assistant_memory_features.py, now in main CLI]**
- Task log and frequent workflow tracking **[✔️ Full: assistant_memory_features.py, now in main CLI]**
- All features are modular and now accessible directly from the main CLI (no separate script required)

---

### 🛠️ Performance Modes
- `default`: Balance performance and features **[✔️ Full: config/profiles]**
- `study`: Focused on notes, calendar, polish **[Planned]**
- `creative`: Enables image/audio/gen tools **[Planned]**
- `focus`: Minimal UI, distraction blocker, alerts **[Planned]**
- `gaming`: Suspends models, silent mode **[✔️ Full: memory.py, CLI: gaming, resume]**
- `low-power`: Tiny model only, no background ops **[✔️ Full: memory.py, CLI: low-power, resume]**

---

### 🔐 Safety & Confirmation
- Always asks before:
  - Creating, modifying, deleting files **[✔️ Full: memory.py, CLI: approve, preview-diff, dry-run, safe_write_file, safe_delete_file]**
  - Backing up vault **[✔️ Full: backup.py, CLI prompt]**
  - Running git operations **[✔️ Full: backup.py, CLI prompt]**
- CLI approval system (`jarvis approve`) **[✔️ Full: memory.py, CLI: approve]**
- Preview of changes/diff before action **[✔️ Full: memory.py, CLI: preview-diff]**
- Auto-backup before any major action **[✔️ Full: backup.py]**
- Dry-run mode available **[✔️ Full: memory.py, CLI: dry-run]**

---

### 🧾 CLI + Daemon Control
- Background daemon with status reporting **[Planned]**
- CLI commands for:
  - `jarvis summarize` **[✔️ Full: summarize.py, modular, LLM-powered, dynamic timeout]**
  - `jarvis polish` **[✔️ Full: polish.py, modular, LLM-powered]**
  - `jarvis set-mode` **[✔️ Full: memory.py, CLI/profile switching, persistent]**
  - `jarvis mode` **[✔️ Full: memory.py, CLI: show current mode]**
  - `jarvis add-feature` **[Planned]**
  - `jarvis backup` **[✔️ Full: backup.py, modular, PAT/SSH]**
  - `jarvis uninstall` **[Planned]**
  - `jarvis note_polish` **[✔️ Full: note_polish.py, now in main CLI]**
  - `jarvis code_explain` **[✔️ Full: code_explain.py, now in main CLI]**
  - `jarvis context_note` **[✔️ Full: context_note.py, now in main CLI]**
  - `jarvis refactor` **[✔️ Full: refactor.py, now in main CLI]**
  - `jarvis interest_features` **[✔️ Full: interest_features.py, now in main CLI]**
  - `jarvis assistant_memory_features` **[✔️ Full: assistant_memory_features.py, now in main CLI]**
- Feature toggles from `feature_registry.json` **[✔️ Full]**

---

## 🆕 Modular Features Now in Main CLI

All modular features previously only available via `modular_cli.py` are now fully integrated into the main CLI (`main.py`). You can access:
- Note polishing (`note_polish`)
- Code explanation (`code_explain`)
- Context-aware note generation (`context_note`)
- Note refactoring (`refactor`)
- Interest/topic enhancements (`interest_features`)
- Assistant memory and feature learning (`assistant_memory_features`)

Use these commands directly in the main CLI prompt. See in-app help or source for usage details.

---

## 📦 Models in Use

| Model         | Use Case                     | RAM Use | Notes |
|---------------|------------------------------|---------|-------|
| TinyLlama     | Lightweight assistant         | ~2.5 GB | Default always-on |
| Mistral 7B    | Summarization, smart polish   | ~6–8 GB | Triggered only on-demand |
| LLaMA 3 7B    | Smart linking, deeper refactor| ~8–10 GB| Optional |
| CodeLLaMA     | Code explanation, fallback    | ~8–10 GB| Optional |
| Stable Diffusion | Creative image generation | ~4–6 GB VRAM | Manual only |
| Whisper / Vosk| Speech recognition            | ~1 GB   | Configurable |
| TTS: Coqui / pyttsx3 | Voice output           | ~100 MB | Lightweight |

All LLMs run via **Ollama**, **llama.cpp**, or **GPTQ** depending on platform.

---

## 💻 System Requirements (Recommended)

| Component | Recommended Minimum for Full Experience |
|----------|-------------------------------------------|
| **CPU**  | Ryzen 7 7435HS or better (8+ cores)       |
| **RAM**  | 16 GB DDR5                                |
| **GPU**  | NVIDIA RTX 4060 Laptop (8 GB VRAM)        |
| **Disk** | 400+ GB SSD free                          |
| **OS**   | Windows 11 with WSL2 (or Linux Dual Boot) |
| **Cooling** | Good thermals (dual-fan or better)     |

✅ You already **meet or exceed** this spec.  
⚙️ System uses throttling, sleep mode, and suspend profiles to ensure **zero bottleneck during gaming, dev work, or creative tasks**.

---

## 📁 Project Structure (Scaffold)

~~~
Jarvis/  
├── main.py  
├── config.json  
├── feature_registry.json  
├── /modules/  
│ └── polish.py, summarize.py, etc.  
├── /memory/  
│ └── assistant_context.json, prefs.json, task_log.json  
├── /llm/  
│ └── local model configs  
├── /tools/  
│ └── uninstall.py, daemon.py  
├── /dashboard/  
├── /vaults/ (optional: linked)  
├── logs/  
├── roadmap.md  
├── README.md
~~~


---

## 🛣️ What's Next

- 🛠️ Step-by-step setup guide (coming next)
- 🔧 Initial scaffolding: config, memory, CLI, model runner
- 🚀 First feature module: note cleanup + summarization
- 🧠 Integration with persistent memory
- 🌐 Optional: Git + Calendar sync setup

## Dynamic Timeout and Progress
- LLM requests now use a dynamic timeout based on input size (30s base + 10s per 500 chars, up to 600s).
- The program prints prompt length, timeout, and actual LLM request time for transparency and debugging.
- Large input detection warns the user and progress spinners are shown for all long-running operations.

## Summarization and Large Input Handling
- Summarization works reliably for very large notes.
- Timeout and progress feedback ensure the user is always informed.


#### References


