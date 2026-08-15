import os
import sys
import platform
import subprocess
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from pathlib import Path

console = Console()

REQUIREMENTS_FILE = "requirements.txt"
INSTALL_MD = "install_requirements.md"
SETUP_SH = "setup_env.sh"
MODULES_DIR = "modules"

SYSTEM_DEPENDENCIES = [
    {"name": "Ollama", "check": ["ollama", "--version"], "desc": "Local LLM runner (https://ollama.com/)"},
    {"name": "Git", "check": ["git", "--version"], "desc": "Version control and backup"},
    {"name": "FFmpeg", "check": ["ffmpeg", "-version"], "desc": "Audio/video processing (optional)"},
    {"name": "WSL2", "check": ["wsl.exe", "--status"], "desc": "Linux subsystem for Windows (if on Windows)"},
    {"name": "Whisper/Vosk", "check": None, "desc": "Speech recognition (Python package or binary)"},
    {"name": "TTS (Coqui/pyttsx3)", "check": None, "desc": "Text-to-speech (Python package)"},
]

def parse_requirements():
    reqs = set()
    if os.path.exists(REQUIREMENTS_FILE):
        with open(REQUIREMENTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("//"):
                    reqs.add(line)
    return reqs

def scan_python_imports():
    imports = set()
    for root, _, files in os.walk(MODULES_DIR):
        for fname in files:
            if fname.endswith(".py"):
                with open(os.path.join(root, fname), "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("import ") or line.startswith("from "):
                            parts = line.replace("import", " ").replace("from", " ").split()
                            if parts:
                                imports.add(parts[0])
    return imports

def check_system_dep(dep):
    if dep["check"] is None:
        return "(Python package or manual)", False
    try:
        result = subprocess.run(dep["check"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=(platform.system()=="Windows"))
        if result.returncode == 0:
            return "Installed", True
        else:
            return "Not found", False
    except Exception:
        return "Not found", False

def write_install_md(py_reqs, sys_deps):
    with open(INSTALL_MD, "w", encoding="utf-8") as f:
        f.write("# Jarvis Environment Setup\n\n")
        f.write("## Python Requirements\n\n")
        for req in sorted(py_reqs):
            f.write(f"- `{req}`\n")
        f.write("\n## System Dependencies\n\n")
        for dep in sys_deps:
            f.write(f"- **{dep['name']}**: {dep['desc']}\n")
        f.write("\n---\n")
        f.write("Run the following to install Python packages:\n\n")
        f.write("    pip install -r requirements.txt\n\n")
        f.write("Install system tools using your OS package manager.\n")

def write_setup_sh(py_reqs, sys_deps):
    with open(SETUP_SH, "w", encoding="utf-8") as f:
        f.write("#!/bin/bash\n")
        f.write("# Jarvis environment setup script\n\n")
        f.write("pip install -r requirements.txt\n")
        for dep in sys_deps:
            if dep["name"] == "Git":
                f.write("sudo apt-get install -y git\n")
            elif dep["name"] == "FFmpeg":
                f.write("sudo apt-get install -y ffmpeg\n")
            elif dep["name"] == "Ollama":
                f.write("# See https://ollama.com/download for platform-specific install\n")
            elif dep["name"] == "WSL2":
                f.write("# WSL2: See https://learn.microsoft.com/en-us/windows/wsl/install\n")
        f.write("# Whisper/Vosk/TTS: install via pip if needed\n")
        f.write("# e.g. pip install openai-whisper vosk pyttsx3 coqui-ai TTS\n")

def print_env_report(py_reqs, sys_deps):
    table = Table(title="Jarvis Environment Report", show_lines=True)
    table.add_column("Dependency", style="bold green")
    table.add_column("Type", style="cyan")
    table.add_column("Status", style="yellow")
    table.add_column("Description", style="white")
    for req in sorted(py_reqs):
        table.add_row(req, "Python", ":white_check_mark:", "Python package")
    for dep in sys_deps:
        status, ok = check_system_dep(dep)
        table.add_row(dep["name"], "System", status, dep["desc"])
    console.print(table)

def env_report(show: bool = False):
    """
    Generate an environment report for Jarvis, including Python and system dependencies.
    Writes install_requirements.md and setup_env.sh. Use --show to print a summary.
    """
    py_reqs = parse_requirements()
    py_reqs |= scan_python_imports()  # Optionally merge imports
    sys_deps = SYSTEM_DEPENDENCIES
    write_install_md(py_reqs, sys_deps)
    write_setup_sh(py_reqs, sys_deps)
    if show:
        print_env_report(py_reqs, sys_deps)
    else:
        console.print(Panel("[green]Environment report written to [bold]install_requirements.md[/bold] and [bold]setup_env.sh[/bold].[/green]", title="Env Report"))
