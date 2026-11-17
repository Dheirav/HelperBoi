# HelperBoi: design

Status: proposal, 2026-11-18. Nothing in section 3 onward is built. Section 1 and 2 are decisions.

HelperBoi is a local assistant for Windows that sets itself up for the machine it is on, then acts on the device when asked ("do this for me", "quiz me on this"). The name is HelperBoi. The code, README and directory were renamed on 2026-11-18 (section 8). The wake word is still "Jarvis" because it is a separate setting.

## 1. The language question

Short answer: Python stays, with three rules that remove the costs that matter. A rewrite would not make a turn faster.

**Where the time and memory actually go.** Model inference runs in Ollama (llama.cpp, native code). Speech recognition with `faster-whisper` runs in CTranslate2 (native code). Embeddings can run in Ollama too. The harness spends its turns waiting on those. So a faster language for the harness does not shorten a turn. What the language does change is idle footprint, startup time, install size, and how easy it is to ship on Windows. Those are the only things worth comparing.

| | Build speed for you | Speech, embeddings, MCP libraries | Ships as | Fits your skills list |
|---|---|---|---|---|
| Python | fastest, and the code exists | best | `uv tool install`, later an installer | yes |
| TypeScript on Node | fast | good for MCP, weak for speech | needs Node or a bundled runtime | yes |
| Go | slower, new language | HTTP sidecars only | one small static `.exe` | no |
| Rust | slowest, new language | young bindings | one small static `.exe` | no |

**The real costs of Python here, and what removes each:**
1. *Weight.* The heavy part of the current install is not Python, it is PyTorch, pulled in by `sentence-transformers`. Drop it from the default install and get embeddings from Ollama (`nomic-embed-text` is 274 MB on its Ollama page).
2. *Idle memory.* Your rule is that nothing stays resident when idle. A CLI that starts, works and exits satisfies it in any language. Speech runs as a short-lived worker process, the pattern already used in screenvoice.
3. *Shipping to non-developers.* Start with `uv tool install` (no Python knowledge needed beyond installing uv). A packaged `.exe` comes later, and packaged Python programs are commonly flagged by antivirus software. I have not measured that here, so test it before promising a download.

**Budgets, set before measuring.** These are guesses with no data behind them. Record the first measurement, then version the numbers (never edit them in place).
- Cold start of a no-op command (`helperboi --version`): 1 second.
- Peak memory of the harness process during a turn, not counting Ollama: 150 MB.
- Install size without models and without PyTorch: 200 MB.

**What would make me switch.** If those budgets are missed after removing PyTorch, or if a packaged build is flagged by antivirus on a clean Windows machine, put a small Go or Rust launcher in front and keep Python for the skills. Not before.

A small Windows-side tray or hotkey host is the one place a different language could help, and only if you later want an always-on listener. Screenvoice already does this with a PowerShell tray that launches Python on demand.

## 2. Decisions already made

- Windows native first. WSL is where it is developed. Windows CI (`windows-latest`) plus a manual run on your machine before claiming support.
- Ollama is required. The setup command checks for it and says how to install it. No bundled `llama.cpp` for now.
- Skills use the Agent Skills layout (`SKILL.md` with a name and a one-line description). Third-party tools come in through MCP, loaded on demand (section 4).
- Portfolio first. Open source if it holds up. The positioning is in `NEXT.md`.

## 3. Architecture

```
user request
   |
   v
[ router ]  matches the request to skill blurbs (no LLM call), picks 1 to 3 skills
   |
   v
[ agent runtime ]  native tool calling, one skill's tools loaded at a time, step limit
   |                     |
   |                     v
   |              [ permission broker ]  risk tier + folder scope + undo + audit log
   v                     |
[ model manager ]        v
 Ollama client,     [ skills ]  files, apps and links, notes, quiz, ...
 hardware profile,         each = SKILL.md + tools
 catalogue, benchmark
   |
   v
[ local profile ]  SQLite: task log, benchmark results, quiz state (docs/QUIZ.md)
```

Interfaces: a CLI first. A tray app or local web page later, only for the setup wizard. Voice is an optional adapter, last.

**Tool registry.** Every tool declares: name, description, a JSON schema for arguments, a risk tier (docs/THREAT-MODEL.md), which folders it may touch, and an undo handler when it changes anything. A tool that is not registered cannot run. The old fallback that asks an LLM to write a new Python tool for an unknown name is removed.

**Why the router decides, not the model.** A 7B model asked to choose whether to load a skill adds a turn and a failure point. Matching the request to the blurbs by embedding similarity costs milliseconds. The evaluation tests both (docs/EVAL.md, conditions B and C).

**Context order.** Stable skill index first, loaded skills appended after it, nothing rewritten above. Rewriting the start of the prompt makes a local model re-read everything after it.

## 4. Skills

```
skills/<name>/SKILL.md      name, one-line description, tools, requires, risk
skills/<name>/tools.py      the tool functions and their schemas
skills/<name>/reference/    anything the skill reads on demand
```

Always in context: the index, one line per skill. Loaded on demand: the chosen skill's text and tool schemas. A skill may declare `requires` (the quiz skill needs files). Loading a skill never grants permission. Blurbs written by third parties are untrusted input.

First skills: `files`, `apps` (open an app, a folder or a link), `notes`, `quiz`. Everything else is later.

## 5. What happens to the existing HelperBoi code

| Keep | Rewrite | Move out as an optional plugin |
|---|---|---|
| path guard and its tests | `agent_loop.py` (regex ReAct) | Obsidian note polishing, splitting, linking |
| approval queue and dry-run mode | `model_router.py` (hard-coded list becomes the catalogue) | interest charts and word clouds |
| `platform_compat.py` | `skill_builder.py` (runs model-written code) | refactor scheduling |
| memory and task log concepts | `voice_activation.py` (online speech input) | |
| adversarial test suite | `tools_extension.py` (one big dispatch) | |

`python_repl` (`eval`/`exec`) and `open_app` (`shell=True`) were not audited. They are replaced, not fixed.

## 6. Hardware profiles used for testing

| Id | Profile | Real or simulated |
|---|---|---|
| P0 | This machine: RTX 4060 with 8.19 GB VRAM, of which 1.8 to 2.2 GB was used by other apps when measured for screenvoice | real |
| P1 | CPU only, on this machine's CPU (the `.wslconfig` comment says Ryzen 7 7435HS, 8 cores, 16 threads) | real. To hide the GPU from Ollama, check its documentation for the current setting. |
| P2 | Low memory: WSL capped to 4 GB in `.wslconfig` | real for Linux runs, not for Windows native |
| P3 | 6 GB and 12 GB or more of VRAM | simulated: tests the recommendation logic only, no performance claim |
| P4 | Two or three other people's machines, ideally one AMD or Intel GPU, one laptop with only integrated graphics, one with 12 GB or more of VRAM | real, collected by hand: `helperboi bench` writes a JSON file the person sends back. No telemetry. |

Not supported yet: macOS, Apple Silicon, native Linux. State that in the README instead of leaving it implied.

The claim "adapts to your hardware" is only as strong as this table. With one real machine it is shown on P0 and P1, and the rest is logic tested against fake profiles. Say so in the README.

## 7. Milestones, each one a safe place to stop

After every milestone the tests pass, `NEXT.md` is current, and the README matches reality. Pause for the FYP whenever it needs the time, after finishing the milestone in progress.

| | Deliverable | Evidence |
|---|---|---|
| M0 | These documents, the task set, the thresholds, committed | the commit |
| M1 | Tool registry, permission broker, `files` skill, unified path guard; runner validated with a scripted fake model | unit tests pass, safety tasks blocked 100 percent |
| M2 | Evaluation runner and the 28 tasks, one model, condition A, on P0 | first pass rate and latency, full run only |
| M3 | Skill index, router, conditions B and C | the three-way comparison in docs/EVAL.md |
| M4 | `helperboi setup`: hardware profile, catalogue, download with a rate-derived ETA, on-machine benchmark | P0 and P1 measured |
| M5 | Quiz skill, cloze mode first | grounding rate, grading agreement (docs/QUIZ.md) |
| M6 | Windows CI, `uv tool install`, README with reproducible numbers, rename strings | a clean Windows machine reproduces the numbers |
| M7 | Optional: local speech in and out | stage latency |

"Done enough for the portfolio" means M0 to M4 and a minimal M6. M5 and M7 are extras.

## 8. Rename: HelperBoi

Done on 2026-11-18: directory `~/Code/HelperBoi`, user-visible strings, logger names (`helperboi.*`), prompts, and the Windows autostart registry name (`HelperBoiAssistant`). An autostart entry called `JarvisAssistant` from an older install would have to be removed by hand, since the code no longer looks for it. One web search found no project called HelperBoi (the nearest were `HelperBot` and `github-helperbot`), which is weak evidence, so check again before a public release.

Left for later: an installable package and command named `helperboi` (the code is still flat `modules/` plus `main.py`, so there is nothing to install yet, which belongs in M1 to M6), and the wake word default.
