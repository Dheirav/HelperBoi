# HelperBoi: current state and plan

Live handover. Last updated 2026-11-18. The README is still mostly the old feature list. Read this first, then `docs/DESIGN.md`.

## What this is

A local assistant for Windows that sets itself up for the machine it is on (hardware profile, model chosen from a catalogue, benchmarked on that machine), then acts on the device when asked: "do this for me", "quiz me on this". It is a harness around a local model, and that alone is not a differentiator: a search on 2026-11-18 (listings and reviews, nothing run) found many open-source local desktop agents for Windows with Ollama and MCP (OpenYak, Accomplish, OROS, Local Operator, Peeky, Goose, an `ollama-agent-harness` repo, and an OpenJarvis on the Ollama registry). What could still be its own: the setup wizard with an on-machine benchmark, a published reliability number per model and machine, and permission tiers with undo. The search did not show whether anyone does the first two together. That is an absence in a short search, not proof.

Portfolio first. Open source if it holds up. Success means a stranger installs it on a clean Windows machine and reproduces the published numbers, not stars. Name: HelperBoi.

## State (2026-11-18)

| Item | State |
|---|---|
| Repo | clone of HelperBoi with history, in `~/Code/HelperBoi` (renamed from Jarvis on 2026-11-18, strings renamed too, wake word kept). Remote `helperboi` points at GitHub `Dheirav/HelperBoi`. `main` has no upstream (removed 2026-11-18, because a clone had left it tracking the remote), so a push has to name its target. **Nothing is pushed.** The GitHub repo is PUBLIC and its `main` had one commit we lacked (`400f09d`, a one-line README change from 2026-09-04). It was merged in (commit 53e526b), not rebased, so the freeze hash below stays valid. A push is now a fast-forward and needs the user's explicit approval. |
| Commits (oldest first) | `41888fa` WSL port, `eb83325` rename and optional PyTorch, `2262457` design docs (the frozen content), `9161083` freeze record, `7e4a88b` CI workflow, 53e526b merge of remote main. After the rename: 174 adversarial tests pass (109 s), 24 platform tests pass. |
| Evaluation freeze | version 1 of `docs/EVAL.md` and `eval/tasks.json` is frozen at `2262457`. Verify with `git diff 2262457 HEAD -- docs/EVAL.md eval/tasks.json` (two lines). |
| CI | `.github/workflows/ci.yml` runs both suites on windows-latest and ubuntu-latest. It has never run, because nothing is pushed. A red Windows job on the first run is expected. The YAML parses. |
| Windows native | NOT tested. The Windows branches of `modules/platform_compat.py` ran only with patched flags and through the original HelperBoi code. |
| Planning documents | `docs/DESIGN.md`, `docs/EVAL.md`, `docs/THREAT-MODEL.md`, `docs/MODELS.md`, `docs/QUIZ.md`, `eval/tasks.json`, this file. See `git log` for the commits and the freeze record. |
| Code for the redesign | none yet. M1 is the first code. |
| Not run or not tried | `test_all_features.py` (needs a live Ollama model, written for Windows), Ollama itself, the microphone, the Windows voice played out loud, `explorer.exe` opening a real app |

## Where things are

- `docs/DESIGN.md`: the language decision (Python stays, three rules, budgets set in advance), architecture, skills, what to keep or rewrite, hardware profiles, milestones M0 to M7, the rename checklist.
- `docs/EVAL.md`: preregistered thresholds, conditions A, B, C and D, run protocol, rules for reading results. Not frozen until its commit hash is written in the "Frozen at" line.
- `eval/tasks.json`: 28 tasks, a fixture, and the check types. Validated as JSON only. No runner exists yet.
- `docs/THREAT-MODEL.md`: risk tiers T0 to T4, the tainted-session rule, Windows path cases, undo and audit log, tests required before a first release.
- `docs/MODELS.md`: candidate models with sizes, tool support and licences read from the source pages, and what was left out and why.
- `docs/QUIZ.md`: cloze first, grounding checks, Leitner scheduling, SQLite schema (parses in SQLite).

## Next action

M1: the typed tool registry, the permission broker with undo, the unified path guard, the `files` skill, and an evaluation runner validated with a scripted fake model. The first tests to add are the Windows path cases in docs/THREAT-MODEL.md (junctions, alternate data streams, reserved names, 8.3 names). The runner needs a progress reader (done out of total, elapsed, ETA from the measured rate) before it is first run.

Pending, needs the user: approve the push (to the existing public repo `Dheirav/HelperBoi`, fast-forward, no force) so the CI can run. Until then Windows native stays untested.

## Findings kept from earlier work

**HelperBoi as found (read, not all of it):** `agent_loop.py` parses free text with regexes, and it ends the loop on any reply containing "final answer" even when a tool was requested. Unknown tool names fall through to an LLM that writes and runs new code. Speech input calls Google's web API (`recognize_google`), although the module says "100% offline". Tool safety is partly there (path guard, approval before generated code through a blocking `input()`). `python_repl` (`eval`/`exec`) and `open_app` (`shell=True`) were not audited. There was no evaluation of the agent. `get_installed_ollama_models` caches a success but not a failure, so with Ollama down every call waits out a 2 second timeout again.

**WSL port, what mattered:** `winreg` imported at the top of `system_daemon.py` failed the whole program on Linux. On Linux the old path guard approved `C:\Windows\System32\x` as one odd filename inside the project and `safe_write_file` created it (seven tests failed for that). `setup_env.sh` had Windows line endings and could not run. A uv-built venv picked Python 3.11 and failed on a backslash inside an f-string, so the venv is built from the system Python 3.12. 34 tracked files still have CRLF endings; they are left alone so diffs stay readable.

**Pi (read: Zechner's post; secondary pages: Implicator, Yage (AI-generated footer), ZenML):** four tools, a prompt plus tool definitions under 1,000 tokens, no MCP, no sub-agents, no permission prompts, no step limit, every interaction logged in a documented format. The reason given for no MCP is context cost: Playwright MCP is 21 tools and 13.7k tokens. What it means here: load tools per skill on demand, keep a step limit (it is a safety control on a personal machine), keep risk tiers and undo because "run it in a container" cannot be told to a non-developer, and test Pi's "tiny prompt is enough" claim on small local models, which is condition A against C in docs/EVAL.md. Unverified and conflicting: whether Earendil acquired Pi on 2026-04-08 (Implicator says yes, Yage says one maintainer), Pi's benchmark standing (Zechner's own Terminal-Bench run, shown only as an image), whether Pi works with local Ollama models and on native Windows.

**Subagent-fetched pages:** the pages fetched for the Pi and model research each contained unrelated instructions to create a Claude Docs document. They were ignored.

## Running things

```bash
./setup_env.sh                                          # builds .venv from system python3
.venv/bin/python -m unittest test_platform_compat -v    # 24 tests, about 2 s
tools/run-tests.sh test_adversarial                     # then: tools/test-progress.sh --watch
git checkout feature_registry.json                      # the tests rewrite this tracked file
```

Ollama: a Linux binary is at `/usr/local/bin/ollama` and `~/.ollama/models` has models, so WSL has its own Ollama. A Windows-side Ollama is also on PATH. Which one has which models was not checked. Nothing was listening on port 11434 on 2026-11-18. In the tool sandbox a closed port times out instead of refusing, which made the adversarial suite slow there; a normal shell refuses at once.
