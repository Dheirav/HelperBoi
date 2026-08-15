from modules.backup import backup_vault  # 👈 NEW
from modules.model_router import select_best_model_for_task, get_llm_model, LLM_MODELS
from modules import memory as mem
from modules import daemon_control, feature_manager
from modules import vector_search
from modules.llm_client import call_ollama as shared_call_ollama
import json
import requests
import os
import subprocess
import signal
import click
import time
import sys
import threading
from modules import refactor as refmod
from modules.skill_engine import list_skills

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

console = Console()

# --- Constants ---
def load_config():
    with open("config.json") as f:
        return json.load(f)

config_data = load_config() if os.path.exists("config.json") else {}
# No baked-in default: the vault sits somewhere different on every machine.
# Set obsidian_vault_path in config.json, or the OBSIDIAN_VAULT_PATH env var.
OBSIDIAN_VAULT_PATH = (
    config_data.get("obsidian_vault_path")
    or os.environ.get("OBSIDIAN_VAULT_PATH", "")
)

# --- LLM integration helpers ---
def call_ollama_mistral(prompt, endpoint="http://localhost:11434", model="mistral:latest"):
    """
    Calls the local Ollama server with the Mistral model for a prompt and returns the response.
    """
    return shared_call_ollama(prompt, endpoint=endpoint, model=model, timeout=30)
# --- End LLM integration helpers ---

# --- Summarization feature (LLM-powered) ---
def summarize_note(note, config=None, model_id=None):
    """
    Summarize a note using the local Mistral LLM via Ollama.
    """
    if not note.strip():
        return "(No content to summarize)"
    prompt = f"Summarize the following note in 1-2 sentences:\n{note.strip()}"
    return call_llm(prompt, model_id=model_id)
# --- End summarization feature ---

# --- Polish feature (LLM-powered) ---
def polish_note_llm(note, config=None, model_id=None):
    """
    Polish and clean up a note using the local Mistral LLM via Ollama.
    """
    if not note.strip():
        return "(No content to polish)"
    prompt = f"Polish and clean up the following note, fixing grammar, formatting, and making it clear and concise.\n{note.strip()}"
    return call_llm(prompt, model_id=model_id)
# --- End polish feature ---

def load_features():
    with open("feature_registry.json") as f:
        return json.load(f)


# --- Interactive UI Preference & Toggle Menus ---
def show_mode_selector():
    mode_table = Table(title="🧠 Select Assistant Operating Mode", header_style="bold magenta", border_style="bright_blue")
    mode_table.add_column("Option #", style="bold yellow", justify="center")
    mode_table.add_column("Mode", style="bold cyan")
    mode_table.add_column("Description", style="white")

    modes = [
        ("1", "default", "Standard mode with all features enabled"),
        ("2", "gaming", "Suspend all LLM models to free 100% GPU VRAM"),
        ("3", "low-power", "Minimal resource overhead, TinyLlama only"),
        ("4", "study", "Optimized for learning, note polishing & summarization"),
        ("5", "creative", "Enables creative tools, image & audio generation"),
        ("6", "focus", "Blocks distractions & background operations")
    ]
    for opt, name, desc in modes:
        mode_table.add_row(opt, name, desc)

    console.print(mode_table)
    choice = input("Select mode number (1-6): ").strip()
    mode_dict = {"1": "default", "2": "gaming", "3": "low-power", "4": "study", "5": "creative", "6": "focus"}
    if choice in mode_dict:
        selected_mode = mode_dict[choice]
        if selected_mode == "gaming":
            mem.suspend_all_models()
            mem.set_silent_mode(True)
        elif selected_mode == "low-power":
            mem.enforce_low_power_mode()
        else:
            mem.set_mode(selected_mode)
        console.print(f"[bold green]✅ Mode set to '{selected_mode}'[/bold green]")
    else:
        console.print("[yellow]Invalid selection.[/yellow]")


def show_feature_toggle_menu():
    all_features = [
        "summarize", "polish", "smart_link", "code_explain", "refactor",
        "vector_search", "context_note", "backup", "git_backup",
        "analyze_notes", "interest_features", "assistant_memory_features",
        "image_gen", "audio_gen", "creative_tools"
    ]
    enabled = set(mem.get_enabled_features())

    feat_table = Table(title="🔌 Feature Toggle Manager", header_style="bold magenta", border_style="bright_blue")
    feat_table.add_column("#", style="bold yellow", justify="center")
    feat_table.add_column("Feature", style="bold cyan")
    feat_table.add_column("Status", style="bold white")

    for idx, feat in enumerate(all_features, 1):
        status = "[bold green]ENABLED[/bold green]" if feat in enabled else "[bold red]DISABLED[/bold red]"
        feat_table.add_row(str(idx), feat, status)

    console.print(feat_table)
    choice = input("Enter feature # to toggle ON/OFF (or press Enter to return): ").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(all_features):
        selected_feat = all_features[int(choice) - 1]
        if selected_feat in enabled:
            mem.disable_feature(selected_feat)
            console.print(f"[bold red]❌ Feature '{selected_feat}' DISABLED[/bold red]")
        else:
            mem.enable_feature(selected_feat)
            console.print(f"[bold green]✅ Feature '{selected_feat}' ENABLED[/bold green]")


def show_preferences_menu():
    prefs = mem.get_preferences()

    table = Table(title="⚙️ Jarvis Preferences & Settings", header_style="bold magenta", border_style="bright_blue")
    table.add_column("Option #", style="bold yellow", justify="center")
    table.add_column("Setting", style="bold cyan")
    table.add_column("Current Value", style="bold white")
    table.add_column("Type / Selectable Values", style="dim")

    table.add_row("1", "Mode", f"[green]{mem.get_mode()}[/green]", "default, gaming, low-power, study, creative, focus")
    table.add_row("2", "Dry-Run Mode", f"[{'green' if mem.is_dry_run() else 'red'}]{mem.is_dry_run()}[/]", "True / False (Toggle)")
    table.add_row("3", "Summarize EOD", f"[{'green' if prefs.get('summarize_eod') else 'red'}]{prefs.get('summarize_eod')}[/]", "True / False (Toggle)")
    table.add_row("4", "Background Ops", f"[{'green' if prefs.get('background_ops') else 'red'}]{prefs.get('background_ops')}[/]", "True / False (Toggle)")
    table.add_row("5", "Calendar Integration", f"[{'green' if prefs.get('calendar_enabled') else 'red'}]{prefs.get('calendar_enabled')}[/]", "True / False (Toggle)")
    table.add_row("6", "Distraction Blocking", f"[{'green' if prefs.get('distraction_block') else 'red'}]{prefs.get('distraction_block')}[/]", "True / False (Toggle)")
    table.add_row("7", "Feature Toggles", f"[cyan]{len(mem.get_enabled_features())} features enabled[/cyan]", "Manage individual ON/OFF feature toggles")

    console.print(table)
    console.print("[dim]Select an option number to edit/toggle (or press Enter to return):[/dim]")

    sel = input("> ").strip()
    if not sel:
        return

    if sel == "1":
        show_mode_selector()
    elif sel == "2":
        new_val = not mem.is_dry_run()
        mem.set_dry_run_mode(new_val)
        console.print(f"[bold green]✅ Dry-Run Mode set to {new_val}[/bold green]")
    elif sel in ("3", "4", "5", "6"):
        key_map = {
            "3": ("summarize_eod", "Summarize EOD"),
            "4": ("background_ops", "Background Ops"),
            "5": ("calendar_enabled", "Calendar Integration"),
            "6": ("distraction_block", "Distraction Blocking")
        }
        key, label = key_map[sel]
        current_val = bool(prefs.get(key, False))
        new_val = not current_val
        mem.set_preference(key, new_val)
        console.print(f"[bold green]✅ {label} toggled to {new_val}[/bold green]")
    elif sel == "7":
        show_feature_toggle_menu()


def show_model_selector():
    table = Table(title="🤖 Select Active LLM Model", header_style="bold magenta", border_style="bright_blue")
    table.add_column("Option #", style="bold yellow", justify="center")
    table.add_column("Model ID", style="bold cyan")
    table.add_column("Model Name", style="bold white")
    table.add_column("Description", style="dim")
    table.add_column("VRAM/RAM", style="yellow")

    table.add_row("1", "qwen2.5-coder:7b", "Qwen 2.5 Coder 7B", "Fast code generation & polishing (Default)", "~4.7 GB")
    table.add_row("2", "qwen2.5-coder:14b", "Qwen 2.5 Coder 14B", "High accuracy code & logic reasoning", "~9.0 GB")
    table.add_row("3", "llama3", "LLaMA 3 8B", "General text & creative writing", "~5.2 GB")
    table.add_row("0", "default", "Auto-Select (Default)", "Automatically pick optimal model per task", "Dynamic")

    console.print(table)
    choice = input("Select model number (0-3): ").strip()
    model_map = {
        "1": "qwen2.5-coder:7b",
        "2": "qwen2.5-coder:14b",
        "3": "llama3",
        "0": None
    }
    return model_map.get(choice)


def show_summary_level_selector():
    table = Table(title="📝 Select Summary Level", header_style="bold magenta", border_style="bright_blue")
    table.add_column("Option #", style="bold yellow", justify="center")
    table.add_column("Level", style="bold cyan")
    table.add_column("Description", style="white")

    table.add_row("1", "short", "Concise 1-2 sentence overview")
    table.add_row("2", "medium", "Balanced bullet points & key highlights (Default)")
    table.add_row("3", "detailed", "Comprehensive section-by-section breakdown")

    console.print(table)
    choice = input("Select level (1-3) [default: 2]: ").strip()
    level_map = {"1": "short", "2": "medium", "3": "detailed"}
    return level_map.get(choice, "medium")


def show_smartlink_mode_selector():
    table = Table(title="🔗 Select Smart-Link Mode", header_style="bold magenta", border_style="bright_blue")
    table.add_column("Option #", style="bold yellow", justify="center")
    table.add_column("Action", style="bold cyan")
    table.add_column("Description", style="white")

    table.add_row("1", "Single Note", "Enrich note with smart links and backlinks as a single note")
    table.add_row("2", "Split Zettelkasten", "Automatically split note into atomic Zettelkasten markdown notes")

    console.print(table)
    choice = input("Select mode (1-2) [default: 1]: ").strip()
    return choice == "2"


def show_interest_tool_selector():
    table = Table(title="📊 Interest & Topic Analysis Tools", header_style="bold magenta", border_style="bright_blue")
    table.add_column("Option #", style="bold yellow", justify="center")
    table.add_column("Tool", style="bold cyan")
    table.add_column("Description", style="white")

    tools = [
        ("1", "visualize", "Generate WordCloud visualization of vault interests"),
        ("2", "barchart", "Plot top interest distribution bar chart"),
        ("3", "snapshot", "Save current interest state snapshot"),
        ("4", "list_snapshots", "List past interest snapshots"),
        ("5", "map", "Map detected interests to vault notes"),
        ("6", "group", "Group similar interest clusters"),
        ("7", "export", "Export interest data to JSON"),
        ("8", "recommend", "Recommend notes for a specific interest"),
        ("9", "tag", "Auto-tag notes with detected interests"),
        ("10", "summarize", "Summarize notes grouped by interest topic"),
        ("11", "stale", "Find stale/inactive interest topics"),
        ("12", "similar", "Find similar interest topics")
    ]
    for opt, name, desc in tools:
        table.add_row(opt, name, desc)

    console.print(table)
    choice = input("Select tool number (1-12): ").strip()
    tool_map = {str(i): tools[i-1][1] for i in range(1, len(tools) + 1)}
    return tool_map.get(choice)


def show_assistant_memory_selector():
    table = Table(title="🧠 Assistant Memory Actions", header_style="bold magenta", border_style="bright_blue")
    table.add_column("Option #", style="bold yellow", justify="center")
    table.add_column("Action", style="bold cyan")
    table.add_column("Description", style="white")

    actions = [
        ("1", "log", "Log user action"),
        ("2", "learn", "Learn feature preference"),
        ("3", "task_log", "Show recent task execution log"),
        ("4", "frequent", "Show most frequent tasks")
    ]
    for opt, name, desc in actions:
        table.add_row(opt, name, desc)

    console.print(table)
    choice = input("Select action number (1-4): ").strip()
    action_map = {"1": "log", "2": "learn", "3": "task_log", "4": "frequent"}
    return action_map.get(choice)


def show_autostart_selector():
    table = Table(title="🚀 Windows Startup Daemon Manager", header_style="bold magenta", border_style="bright_blue")
    table.add_column("Option #", style="bold yellow", justify="center")
    table.add_column("Action", style="bold cyan")
    table.add_column("Description", style="white")

    table.add_row("1", "status", "Check Windows startup registry & daemon state")
    table.add_row("2", "enable", "Enable Jarvis automatic startup on Windows boot")
    table.add_row("3", "disable", "Disable Jarvis automatic startup on boot")

    console.print(table)
    choice = input("Select action (1-3) [default: 1]: ").strip()
    action_map = {"1": "status", "2": "enable", "3": "disable"}
    return action_map.get(choice, "status")


# --- General LLM call ---
def call_llm(prompt, model_id=None):
    model = get_llm_model(model_id)
    if model["type"] == "ollama":
        return call_ollama_mistral(prompt, endpoint=model["endpoint"], model=model["model"])
    return f"(Model type {model['type']} not supported yet)"

class OllamaServerManager:
    def __init__(self, model_name="mistral"):
        self.model_name = model_name
        self.proc = None

    def start(self):
        # Start ollama serve in the background if not already running
        self.serve_proc = subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Start ollama run <model> in the background
        self.proc = subprocess.Popen(["ollama", "run", self.model_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.wait_until_ready()

    def wait_until_ready(self, timeout=60):
        """Wait until the Ollama server is ready to accept requests."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                resp = requests.get("http://localhost:11434/api/tags", timeout=2)
                if resp.status_code == 200:
                    return True
            except Exception:
                pass
            time.sleep(1)
        print("\n❌ Ollama server did not become ready in time. Please check your Ollama installation and model availability.")
        exit(1)

    def stop(self):
        if self.proc:
            self.proc.terminate()
            self.proc.wait()
        if hasattr(self, 'serve_proc') and self.serve_proc:
            self.serve_proc.terminate()
            self.serve_proc.wait()

def show_spinner(message, stop_event):
    spinner = ['|', '/', '-', '\\']
    idx = 0
    while not stop_event.is_set():
        sys.stdout.write(f"\r{message} {spinner[idx % len(spinner)]}")
        sys.stdout.flush()
        idx += 1
        time.sleep(0.1)
    sys.stdout.write("\r" + " " * (len(message) + 2) + "\r")
    sys.stdout.flush()

@click.group()
def cli():
    pass

@cli.command()
@click.argument('note_path', required=False)
@click.option('--level', default='medium', type=click.Choice(['short', 'medium', 'detailed']), help='Summary level: short, medium, or detailed.')
def summarize(note_path, level):
    """Summarize a note with a specified summary level."""
    from modules.summarize import summarize_note
    if not note_path:
        note_path = input('Enter path to note: ')
    summary = summarize_note(note_path, level)
    print(f"Summary ({level}):\n{summary}")

# --- Auto prompt optimization and model routing ---
# (moved to modules/model_router.py
def print_help():
    table = Table(title="🤖 Jarvis Assistant Command Reference", header_style="bold magenta", border_style="bright_blue")
    table.add_column("Command", style="bold cyan")
    table.add_column("Description", style="white")

    table.add_row("status", "View system hardware (CPU/RAM/GPU VRAM) & daemon status")
    table.add_row("polish", "Polish and clean up a note (LLM-powered)")
    table.add_row("summarize", "Summarize a note in short/medium/detailed format")
    table.add_row("code_explain", "Explain code from a file or prompt (LLM-powered)")
    table.add_row("refactor", "Refactor and clean up Python code (LLM-powered)")
    table.add_row("model", "List available LLM models and switch active model")
    table.add_row("backup", "Run Git backup of your Obsidian vault")
    table.add_row("smartlink", "Smart-link and split notes into Zettelkasten atomic notes")
    table.add_row("analyze_notes", "Analyze vault for writing style, note types, and interests")
    table.add_row("vector_search", "Perform semantic vector search over Obsidian notes")
    table.add_row("approve", "Review and execute pending approval requests")
    table.add_row("gaming", "Suspend all LLM models to free 100% GPU VRAM")
    table.add_row("resume", "Resume LLM models and normal mode")
    table.add_row("low-power", "Enable low-power mode (TinyLlama only)")
    table.add_row("mode", "Show current system operating mode")
    table.add_row("prefs", "View and edit user preferences")
    table.add_row("history", "Show recent assistant activity history")
    table.add_row("diagnose", "Run full system diagnostic health audit")
    table.add_row("eval", "Evaluate Python logic or math expression safely")
    table.add_row("read_file", "Safely view file content inside allowed paths")
    table.add_row("write_file", "Safely write content to a file")
    table.add_row("voice", "Launch interactive voice input & speech synthesis mode")
    table.add_row("speak <text>", "Synthesize and speak text out loud using Windows SAPI5")
    table.add_row("clear", "Clear terminal screen")
    table.add_row("exit", "Exit Jarvis shell")

    console.print(table)

def main():
    config = load_config()
    features = load_features()
    ollama_manager = OllamaServerManager(model_name="mistral")
    ollama_manager.start()
    try:
        welcome_panel = Panel(
            Text("🤖 JARVIS AI ASSISTANT\nModular Local LLM Assistant & Skill Engine", justify="center", style="bold cyan"),
            subtitle="[dim]Type 'help' for available commands | 'exit' to quit[/dim]",
            border_style="bright_blue",
            padding=(1, 2)
        )
        console.print(welcome_panel)

        mode = mem.get_mode()
        if mode not in {"default", "gaming", "low-power", "study", "creative", "focus"}:
            mode = "default"
        enabled_features = mem.get_enabled_features()
        
        status_table = Table(show_header=False, box=None, border_style="dim")
        status_table.add_row("[bold yellow]Mode:[/bold yellow]", f"[bold green]{mode}[/bold green]")
        console.print(status_table)
        console.print()

        current_model = None

        def process_unified_command(raw_input, model_id=None, source="text"):
            """
            Unified Command Processor & Intent Dispatcher.
            Guarantees 100% feature parity between Voice Mode and CLI Text Mode.
            """
            raw_text = str(raw_input).strip()
            if not raw_text:
                return ""

            from modules.intent_classifier import classify_intent
            intent_data = classify_intent(raw_text, model_id=model_id)
            intent = str(intent_data.get("intent", "")).lower()
            confidence = intent_data.get("confidence", 0.0)
            params = intent_data.get("params", {})
            target_file = intent_data.get("target_file")

            if source == "text":
                console.print(f"[bold cyan][🧠 Intent Detected]:[/bold cyan] [yellow]{intent.title()}[/yellow] (Confidence: {confidence:.2f})")
                if target_file:
                    console.print(f"   Target File: {target_file}")

            if intent in ("prefs", "pref"):
                show_preferences_menu()
                return "[SUCCESS] Displayed preferences menu."
            elif intent in ("history", "hist"):
                console.print("[bold yellow]Recent Assistant Actions:[/bold yellow]")
                for entry in mem.get_history():
                    console.print(f"[{entry['timestamp']}] [cyan]{entry['action']}[/cyan] {entry.get('meta','')}")
                return "[SUCCESS] Listed recent history."
            elif intent in ("model", "models"):
                console.print("[bold yellow]Available LLM Models:[/bold yellow]")
                table = Table(header_style="bold cyan")
                table.add_column("ID", style="bold yellow")
                table.add_column("Name", style="bold white")
                table.add_column("Description", style="dim")
                table.add_column("VRAM/RAM", style="cyan")
                for m in LLM_MODELS:
                    table.add_row(m['id'], m['name'], m['description'], m['ram'])
                console.print(table)
                return "[SUCCESS] Listed LLM models."
            elif intent in ("status", "sys", "system", "stats"):
                from modules import system_daemon
                st = system_daemon.get_system_status()
                table = Table(title="💻 System & Daemon Status", header_style="bold cyan", border_style="dim")
                table.add_column("Metric", style="bold white")
                table.add_column("Value", style="yellow")
                table.add_row("CPU Usage", f"{st['cpu_usage_percent']}%")
                table.add_row("System RAM", f"{st['ram_used_gb']} GB / {st['ram_total_gb']} GB")
                table.add_row("GPU VRAM", str(st['gpu_vram']))
                table.add_row("Windows Autostart", "ENABLED" if st['autostart_enabled'] else "DISABLED")
                table.add_row("VRAM Auto-Unload", str(st['ollama_keep_alive']))
                console.print(table)
                return "[SUCCESS] Displayed system status."
            elif intent == "backup":
                github_pat = os.getenv("GITHUB_TOKEN")
                console.print("[bold cyan]🗂️ Running Git backup...[/bold cyan]")
                backup_vault(OBSIDIAN_VAULT_PATH, github_pat=github_pat)
                return "[bold green][✅] Backup complete.[/bold green]"
            elif intent == "polish":
                if target_file and os.path.exists(target_file):
                    with open(target_file, encoding='utf-8', errors='ignore') as f:
                        text = f.read()
                    return polish_note_llm(text, model_id=model_id)
                return polish_note_llm(raw_text, model_id=model_id)
            elif intent == "summarize":
                level = params.get("level", "medium")
                if target_file and os.path.exists(target_file):
                    with open(target_file, encoding='utf-8', errors='ignore') as f:
                        text = f.read()
                    return summarize_note(text, level=level, model_id=model_id)
                return summarize_note(raw_text, level=level, model_id=model_id)
            elif intent == "code_explain":
                from modules.code_explain import explain_code
                if target_file and os.path.exists(target_file):
                    with open(target_file, encoding='utf-8', errors='ignore') as f:
                        code = f.read()
                    return explain_code(code, model_id=model_id)
                return explain_code(raw_text, model_id=model_id)
            elif intent == "refactor":
                from modules.refactor import refactor_code
                if target_file and os.path.exists(target_file):
                    with open(target_file, encoding='utf-8', errors='ignore') as f:
                        code = f.read()
                    return refactor_code(code, model_id=model_id)
                return refactor_code(raw_text, model_id=model_id)
            elif intent == "vector_search":
                from modules import vector_search
                q = params.get("query") or raw_text
                console.print(f"🔎 Searching vault for: {q}")
                return str(vector_search.search(q, top_k=5, vault_path=OBSIDIAN_VAULT_PATH))
            elif intent == "in_app_action":
                from modules.tools_extension import handle_in_app_action
                return handle_in_app_action(
                    app_name=params.get("app_name", ""),
                    sub_action=params.get("sub_action", ""),
                    target=params.get("target", "")
                )
            elif intent == "open_app":
                from modules.tools_extension import open_app
                app_name = params.get("app_name") or raw_text
                res = open_app(app_name)
                if "[CAPABILITY_GAP:" in res:
                    from modules.skill_builder import propose_and_build_skill
                    return propose_and_build_skill(app_name, raw_text, model_id=model_id)
                return res
            elif intent in ("open_browser", "google", "browser"):
                from modules.tools_extension import open_browser
                target = params.get("target") or raw_text
                return open_browser(target)
            elif intent == "import_contacts" or raw_text.startswith("import_contacts") or raw_text.startswith("import contacts"):
                from modules.tools_extension import import_contacts_to_registry
                c_file = target_file or params.get("file_path") or raw_text.split()[-1]
                return import_contacts_to_registry(c_file, vault_path=OBSIDIAN_VAULT_PATH)
            elif intent == "create_skill" or raw_text.startswith("learn") or raw_text.startswith("create_skill"):
                from modules.skill_engine import generate_skill_from_prompt
                console.print("[⏳] Generating new custom skill...")
                success, msg = generate_skill_from_prompt(raw_text, model_id=model_id)
                return f"[{'✅' if success else '❌'}] {msg}"
            elif intent == "multi_step_chain":
                from modules.agent_loop import run_agent_loop
                console.print("🤖 Launching Autonomous ReAct Tool Chain...")
                final_ans = run_agent_loop(raw_text, model_id=model_id, vault_path=OBSIDIAN_VAULT_PATH)
                return f"\n[✅ ReAct Loop Result]:\n{final_ans}"
            elif intent in list_skills():
                from modules.skill_engine import execute_skill
                console.print(f"⚡ Executing custom skill '{intent}'...")
                return execute_skill(intent, input_text=raw_text, target_file=target_file)
            else:
                from modules.rag_context import inject_rag_and_call
                return inject_rag_and_call(raw_text, model_id=model_id, vault_path=OBSIDIAN_VAULT_PATH)

        while True:
            cmd = input("> ").strip().lower()
            if cmd in ("exit", "q"):
                break
            elif cmd == "help":
                print_help()
            elif cmd in ("status", "sys", "system", "stats") or cmd.startswith("autostart") or cmd.startswith("daemon"):
                from modules import system_daemon
                parts = cmd.split()
                sub = parts[1] if len(parts) > 1 else show_autostart_selector()
                if sub == "enable":
                    ok, msg = system_daemon.enable_windows_autostart()
                    console.print(f"[{'bold green' if ok else 'bold red'}][{'✅' if ok else '❌'}][/{'bold green' if ok else 'bold red'}] {msg}")
                elif sub == "disable":
                    ok, msg = system_daemon.disable_windows_autostart()
                    console.print(f"[{'bold green' if ok else 'bold red'}][{'✅' if ok else '❌'}][/{'bold green' if ok else 'bold red'}] {msg}")
                else:
                    st = system_daemon.get_system_status()
                    table = Table(title="💻 System & Daemon Status", header_style="bold cyan", border_style="dim")
                    table.add_column("Metric", style="bold white")
                    table.add_column("Value", style="yellow")
                    table.add_row("CPU Usage", f"{st['cpu_usage_percent']}%")
                    table.add_row("System RAM", f"{st['ram_used_gb']} GB / {st['ram_total_gb']} GB")
                    table.add_row("GPU VRAM", str(st['gpu_vram']))
                    table.add_row("Windows Autostart", "ENABLED" if st['autostart_enabled'] else "DISABLED")
                    table.add_row("VRAM Auto-Unload", str(st['ollama_keep_alive']))
                    console.print(table)
            elif cmd in ("clear", "cls"):
                os.system('cls' if os.name == 'nt' else 'clear')
            elif cmd in ("voice", "listen", "speech"):
                from modules import voice_activation
                from modules.tools_extension import sanitize_for_speech

                def _voice_handler(spoken_text):
                    res = process_unified_command(spoken_text, model_id=current_model, source="voice")
                    spoken_summary = sanitize_for_speech(res)
                    if spoken_summary:
                        voice_activation.speak(spoken_summary, block=False)
                    return res

                voice_activation.start_voice_mode(on_command_callback=_voice_handler)
            elif cmd.startswith("speak "):
                from modules import voice_activation
                voice_activation.speak(cmd[6:].strip(), block=True)
            elif cmd in ("diagnose", "health"):
                from modules.tools_extension import system_diagnose
                console.print(system_diagnose(vault_path=OBSIDIAN_VAULT_PATH))
            elif cmd in ("eval", "python", "repl"):
                from modules.tools_extension import python_repl
                expr = input("Enter Python code/expression to evaluate: ").strip()
                console.print(python_repl(expr))
            elif cmd in ("read_file", "read"):
                from modules.tools_extension import read_file
                path = input("Enter file path to read: ").strip()
                console.print(read_file(path))
            elif cmd in ("write_file", "write"):
                from modules.tools_extension import write_file
                path = input("Enter target file path: ").strip()
                content = input("Enter file content: ").strip()
                console.print(write_file(path, content))
            elif cmd in ("pull_model", "pull"):
                m_name = input("Enter Ollama model tag to pull (e.g. qwen2.5-coder:7b): ").strip()
                if m_name:
                    from modules.model_router import pull_ollama_model
                    console.print(f"[bold cyan][⏳] Pulling model '{m_name}' via Ollama...[/bold cyan]")
                    console.print(pull_ollama_model(m_name))
            elif cmd in ("delete_model", "rm_model", "rm-model"):
                m_name = input("Enter Ollama model tag to delete (e.g. codellama:latest): ").strip()
                if m_name:
                    from modules.model_router import delete_ollama_model
                    console.print(f"[bold yellow][⚠️] Deleting model '{m_name}'...[/bold yellow]")
                    console.print(delete_ollama_model(m_name))
            elif cmd in ("model", "models"):
                sel = show_model_selector()
                if sel:
                    if get_llm_model(sel):
                        current_model = sel
                        console.print(f"[bold green]Switched to model: {get_llm_model(sel)['name']}[/bold green]")
                        ollama_manager.stop()
                        ollama_manager = OllamaServerManager(model_name=get_llm_model(sel)["model"])
                        ollama_manager.start()
                        console.print("Waiting for model to become ready...")
                        time.sleep(2)
                    else:
                        console.print("[red]Unknown model id.[/red]")
                else:
                    current_model = None
                    console.print("[bold yellow]Switched to default model auto-selection.[/bold yellow]")
            elif cmd == "polish":
                print("\n📝 Enter a note to polish (type END on a new line to finish):")
                lines = []
                while True:
                    line = input()
                    if line.strip() == "END":
                        break
                    lines.append(line)
                user_note = "\n".join(lines)
                print("\n📝 Polishing Note (LLM):")
                print("Before:", user_note)
                stop_event = threading.Event()
                spinner_thread = threading.Thread(target=show_spinner, args=("[⏳] Sending to LLM for polishing...", stop_event))
                spinner_thread.start()
                # Use auto model selection unless user override
                model_id = current_model or select_best_model_for_task("polish", user_note)
                result = polish_note_llm(user_note, config, model_id=model_id)
                stop_event.set()
                spinner_thread.join()
                print("[✅] Polishing complete.")
                print("After: ", result)
            elif cmd == "summarize":
                print("\n📝 Enter a note to summarize (type END on a new line to finish):")
                lines = []
                while True:
                    line = input()
                    if line.strip() == "END":
                        break
                    lines.append(line)
                user_note = "\n".join(lines)
                if len(user_note) > 2000:
                    console.print("[yellow]⚠️ Large input detected. Processing...[/yellow]")
                level = show_summary_level_selector()
                console.print(f"\n[bold cyan]📝 Summarizing Note (LLM, level: {level}):[/bold cyan]")
                stop_event = threading.Event()
                spinner_thread = threading.Thread(target=show_spinner, args=("[⏳] Sending to LLM for summarization...", stop_event))
                spinner_thread.start()
                model_id = current_model or select_best_model_for_task("summarize", user_note)
                summary = summarize_note(user_note, config, model_id=model_id)
                stop_event.set()
                spinner_thread.join()
                console.print("[bold green][✅] Summarization complete.[/bold green]")
                console.print(f"Summary:\n{summary}")
            elif cmd == "backup":
                github_pat = os.getenv("GITHUB_TOKEN")
                if github_pat:
                    print("\n🔑 Using GitHub PAT from environment for backup.")
                else:
                    print("\n⚠️  No GitHub PAT found in environment variable GITHUB_TOKEN. You may be prompted for credentials or backup may fail.")
                print("\n🗂️ Running Git backup...")
                stop_event = threading.Event()
                spinner_thread = threading.Thread(target=show_spinner, args=("[⏳] Backing up vault...", stop_event))
                spinner_thread.start()
                backup_vault(OBSIDIAN_VAULT_PATH, github_pat=github_pat)
                stop_event.set()
                spinner_thread.join()
                print("[✅] Backup complete.")
            elif cmd == "smartlink":
                print("\n🧠 Enter a note to smart-link (type END on a new line to finish):")
                lines = []
                while True:
                    line = input()
                    if line.strip() == "END":
                        break
                    lines.append(line)
                user_note = "\n".join(lines)
                split = show_smartlink_mode_selector()
                vault_path = OBSIDIAN_VAULT_PATH if os.path.exists(OBSIDIAN_VAULT_PATH) else None
                console.print("[bold cyan][⏳] Sending to LLM for smart linking and splitting...[/bold cyan]")
                from modules.smart_link import smart_link_llm
                model_info = get_llm_model(current_model)
                result = smart_link_llm(user_note, model_info, vault_path=vault_path, split=split)
                console.print("[bold green][✅] Smart linking complete.[/bold green]")
                console.print(result)
            elif cmd == "analyze_notes":
                print("\n🔍 Analyzing notes in the vault for writing style, note types, and interests...")
                from modules.analyze_notes import analyze_notes
                results = analyze_notes(OBSIDIAN_VAULT_PATH)
                print(f"\n📝 Writing Style: {results['style']}")
                print(f"🗂️ Note Types: {', '.join(results['types'])}")
                print(f"⭐ Interests: {', '.join(results['interests'])}")
                print(f"\n📊 Detailed Stats:")
                print(f"  • Total notes: {results['total_notes']}")
                print(f"  • Avg note length: {results['avg_note_len']:.1f} chars")
                print(f"  • Headers used: {results['header_count']}")
                print(f"  • Wikilinks: {results['wikilinks']}")
                print(f"  • Tags: {results['tag_count']}")
                print(f"  • TODOs: {results['todos']}")
                # --- New: Note type and Obsidian feature summary ---
                print("\n🧩 Note Type Breakdown:")
                for ntype, count in results.get('note_type_counts', {}).items():
                    print(f"  - {ntype.title()}: {count}")
                print("\n🔌 Obsidian Feature Usage:")
                for feat, count in results.get('feature_counts', {}).items():
                    print(f"  - {feat}: {count} notes")
            elif cmd == "analyze_notes_dryrun":
                print("\n🔍 [DRY RUN] Simulating optimal batch size and LLM calls for note analysis...")
                from modules.analyze_notes import analyze_notes
                analyze_notes(OBSIDIAN_VAULT_PATH, dry_run=True)
                print("[DRY RUN] Complete.")
            elif cmd == "note_polish":
                # Polish a note from a file
                note_path = input("Enter path to note file: ").strip()
                out_path = input("Output file (optional, leave blank to print): ").strip()
                from modules import note_polish
                with open(note_path, encoding='utf-8') as f:
                    text = f.read()
                model_id = current_model or select_best_model_for_task("note_polish", text)
                result = note_polish.polish_note(text, model_id=model_id) if hasattr(note_polish, 'polish_note') else note_polish.polish_note(text)
                if out_path:
                    with open(out_path, 'w', encoding='utf-8') as f:
                        f.write(result)
                    print(f'Polished note saved to {out_path}')
                else:
                    print(result)
            elif cmd == "code_explain":
                code_path = input("Enter path to code file: ").strip()
                from modules import code_explain
                with open(code_path, encoding='utf-8') as f:
                    code = f.read()
                model_id = current_model or select_best_model_for_task("code_explain", code)
                print(code_explain.explain_code(code, model_id=model_id) if hasattr(code_explain, 'explain_code') else code_explain.explain_code(code))
            elif cmd == "context_note":
                prompt = input("Enter prompt for context-aware note: ").strip()
                vault = input("Vault path (optional, default .): ").strip() or '.'
                from modules import context_note
                model_id = current_model or select_best_model_for_task("context_note", prompt)
                print(context_note.generate_context_note(prompt, vault, model_id=model_id) if hasattr(context_note, 'generate_context_note') else context_note.generate_context_note(prompt, vault))
            elif cmd == "refactor":
                code_path = input("Enter path to code file: ").strip()
                out_path = input("Output file (optional, leave blank to print): ").strip()
                from modules import refactor
                with open(code_path, encoding='utf-8') as f:
                    code = f.read()
                model_id = current_model or select_best_model_for_task("refactor", code)
                result = refactor.refactor_code(code, model_id=model_id) if hasattr(refactor, 'refactor_code') else refactor.refactor_code(code)
                if out_path:
                    with open(out_path, 'w', encoding='utf-8') as f:
                        f.write(result)
                    print(f'Refactored code saved to {out_path}')
                else:
                    print(result)
            elif cmd == "interest_features":
                from modules import interest_features as mod
                action = show_interest_tool_selector()
                if not action:
                    continue
                vault = input("Vault path (optional, press Enter for default): ").strip() or None
                interest = input("Interest/topic (optional, press Enter to skip): ").strip() or None
                out = input("Output file (optional, press Enter to skip): ").strip() or None
                if action == 'visualize':
                    interests = mod.load_detected_interests()
                    mod.visualize_interests(interests, out or 'interest_wordcloud.png')
                elif action == 'barchart':
                    interests = mod.load_detected_interests()
                    mod.plot_interest_barchart(interests, out or 'interest_barchart.png')
                elif action == 'snapshot':
                    interests = mod.load_detected_interests()
                    mod.save_interest_snapshot(interests)
                elif action == 'list_snapshots':
                    console.print('\n'.join(mod.list_interest_snapshots()))
                elif action == 'map':
                    interests = mod.load_detected_interests()
                    notes = mod.load_notes_from_vault(vault or '.')
                    mapping = mod.map_interests_to_notes(interests, notes)
                    mod.export_interest_mapping(mapping, out or 'interest_note_mapping.json')
                elif action == 'group':
                    interests = mod.load_detected_interests()
                    console.print(mod.group_similar_interests(interests))
                elif action == 'export':
                    interests = mod.load_detected_interests()
                    mod.export_interests(interests, out or 'interests_export.json')
                elif action == 'recommend':
                    interests = mod.load_detected_interests()
                    mapping = mod.load_interest_mapping()
                    notes = mod.load_notes_from_vault(vault or '.')
                    recs = mod.recommend_notes_for_interest(interest, mapping, notes)
                    for n in recs:
                        console.print(f"[bold cyan]{n['filename']}:[/bold cyan] {n['content'][:120]}...")
                elif action == 'tag':
                    interests = mod.load_detected_interests()
                    notes = mod.load_notes_from_vault(vault or '.')
                    mod.auto_tag_notes_with_interests(notes, interests)
                elif action == 'summarize':
                    notes = mod.load_notes_from_vault(vault or '.')
                    console.print(mod.summarize_notes_by_interest(interest, notes))
                elif action == 'stale':
                    mapping = mod.load_interest_mapping()
                    notes = mod.load_notes_from_vault(vault or '.')
                    console.print(mod.find_stale_interests(mapping, notes))
                elif action == 'similar':
                    interests = mod.load_detected_interests()
                    console.print(mod.find_similar_interests(interest, interests))
                else:
                    console.print("[red]Unknown action.[/red]")
            elif cmd == "assistant_memory_features":
                from modules import assistant_memory_features as mod
                action = show_assistant_memory_selector()
                if not action:
                    continue
                data = input("Data for action (optional, press Enter to skip): ").strip() or None
                if action == 'log':
                    mod.log_user_action(data)
                elif action == 'learn':
                    mod.learn_feature(data)
                elif action == 'task_log':
                    console.print(mod.get_task_log())
                elif action == 'frequent':
                    console.print(mod.get_frequent_tasks())
                else:
                    console.print("[red]Unknown action.[/red]")
            elif cmd in ("prefs", "pref"):
                show_preferences_menu()
            elif cmd == "history":
                print("Recent assistant actions:")
                for entry in mem.get_history():
                    print(f"[{entry['timestamp']}] {entry['action']} {entry.get('meta','')}")
            elif cmd in ("feature_registry", "features"):
                show_feature_toggle_menu()
            elif cmd == "task_log":
                print("Recent tasks:")
                for entry in mem.get_task_log():
                    print(f"[{entry['timestamp']}] {entry['task']} {entry.get('meta','')}")
            elif cmd == "frequent":
                print("Most frequent tasks:")
                for task, count in mem.get_frequent_tasks():
                    print(f"{task}: {count}")
            elif cmd == "remember":
                instr = input("Enter instruction (e.g. 'Always summarize EOD'): ")
                print(mem.learn_from_nl_instruction(instr))
            elif cmd == "forget":
                instr = input("Enter instruction to forget (e.g. 'Disable summarize'): ")
                print(mem.learn_from_nl_instruction(instr))
            elif cmd == "gaming":
                print("Activating gaming mode: suspending all models and enabling silent mode...")
                mem.suspend_all_models()
                mem.set_silent_mode(True)
                print("Gaming mode active. All LLMs suspended, notifications muted.")
            elif cmd == "resume":
                print("Resuming all models and restoring normal mode...")
                mem.resume_all_models()
                mem.restore_normal_mode()
                print("Normal mode restored.")
            elif cmd == "low-power":
                print("Activating low-power mode: only TinyLlama, no background ops...")
                mem.enforce_low_power_mode()
                print("Low-power mode active. Only TinyLlama enabled, background ops disabled.")
            elif cmd == "refactor-schedule":
                print("Schedule a refactor job.")
                note_path = input("Note file path: ").strip()
                when = input("When (YYYY-MM-DDTHH:MM, UTC): ").strip()
                repeat = input("Repeat (none/daily/weekly): ").strip().lower() or None
                job_id = refmod.schedule_refactor(note_path, when, repeat)
                print(f"Scheduled refactor job {job_id}.")
            elif cmd == "refactor-jobs":
                print("Scheduled refactor jobs:")
                for job_id, job in refmod.list_refactor_jobs().items():
                    print(f"{job_id}: {job}")
            elif cmd == "refactor-remove":
                job_id = input("Job ID to remove: ").strip()
                if refmod.remove_refactor_job(job_id):
                    print("Job removed.")
                else:
                    print("Job not found.")
            elif cmd == "refactor-scheduler":
                print("Starting background refactor scheduler (checks every hour)...")
                refmod.start_refactor_scheduler()
                print("Scheduler started in background.")
            elif cmd in ("set-mode", "mode"):
                show_mode_selector()
            elif cmd == "approve":
                entry = mem.approve_next_action()
                if entry:
                    if mem.execute_approved_action(entry):
                        print("[✅] Approved action executed.")
                    else:
                        print("[⚠️] Approved action could not be executed.")
            elif cmd == "dry-run":
                enable = input("Enable dry-run mode? (y/n): ").strip().lower() == 'y'
                mem.set_dry_run_mode(enable)
                print(f"Dry-run mode {'enabled' if enable else 'disabled'}.")
            elif cmd == "preview-diff":
                file_path = input("File to diff: ").strip()
                new_content = input("Paste new content (end with END):\n")
                lines = []
                while True:
                    l = input()
                    if l.strip() == "END":
                        break
                    lines.append(l)
                mem.preview_diff(file_path, '\n'.join(lines))
            elif cmd == "vector_search":
                print("\n🔎 Semantic search over notes (local embeddings)")
                q = input("Enter search query: ").strip()
                vault = input("Vault path (default ./vaults): ").strip() or "./vaults"
                top_k = input("Number of results (default 5): ").strip()
                top_k = int(top_k) if top_k.isdigit() else 5
                reindex = input("Reindex embeddings first? (y/N): ").strip().lower() == 'y'
                if reindex:
                    vector_search.build_embeddings(vault)
                vector_search.search(q, top_k, vault)
            elif cmd == "note_generate":
                print("\n🧠 Zettelkasten Atomic Note Generation")
                print("Paste topics (one per line, blank line to end):")
                topics = []
                while True:
                    line = input()
                    if not line.strip():
                        break
                    topics.append(line.strip())
                print("Paste subtopics (one per line, blank line to end, or just Enter to skip):")
                subtopics = []
                while True:
                    line = input()
                    if not line.strip():
                        break
                    subtopics.append(line.strip())
                print("Paste rough notes (type END on a new line to finish, or just Enter to skip):")
                rough_lines = []
                while True:
                    line = input()
                    if line.strip() == "END":
                        break
                    rough_lines.append(line)
                rough_notes = "\n".join(rough_lines) if rough_lines else None
                context = input("Optional: Add extra context for note content (or just Enter to skip): ").strip() or None
                from modules.note_generation import NoteGenerator
                output_dir = input("Output directory for notes (default: test_vault): ").strip() or "test_vault"
                note_gen = NoteGenerator(output_dir=output_dir)
                print("\n[⏳] Generating atomic note headers and notes...")
                file_paths = note_gen.run_workflow(topics, subtopics=subtopics or None, rough_notes=rough_notes, context=context)
                print(f"[✅] Note generation complete. {len(file_paths)} notes saved to {output_dir}.")
                for fp in file_paths:
                    print(f"  - {fp}")
            else:
                # Unified Natural Language Intent Classifier & Command Router
                print("[⏳] Classifying intent...")
                result = process_unified_command(cmd, model_id=current_model, source="text")
                if result:
                    print(result)




    finally:
        # Stop Ollama server/model
        ollama_manager.stop()

if __name__ == "__main__":
    main()