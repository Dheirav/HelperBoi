import json
import os
from datetime import datetime
import subprocess
import psutil
import difflib
import threading
import time

# Global file lock for thread-safe JSON persistence
_file_lock = threading.Lock()

MEMORY_DIR = os.path.join(os.path.dirname(__file__), '..', 'memory')
ASSISTANT_CONTEXT_PATH = os.path.join(MEMORY_DIR, 'assistant_context.json')
USER_PREFS_PATH = os.path.join(MEMORY_DIR, 'user_preferences.json')
NOTE_STRUCTURE_MEMORY_PATH = os.path.join(MEMORY_DIR, 'note_structure_memory.json')
TASK_LOG_PATH = os.path.join(MEMORY_DIR, 'task_log.json')
APPROVAL_QUEUE_PATH = os.path.join(MEMORY_DIR, 'approval_queue.json')
DRY_RUN_PREF_KEY = 'dry_run_mode'

# --- Assistant Behavior, Preferences, History ---
def load_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        # If file is empty or invalid, return default
        return default if default is not None else {}

def save_json(path, data):
    """Atomically save data to a JSON file to prevent corruption. Thread-safe with retry."""
    with _file_lock:
        dir_name = os.path.dirname(path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        temp_path = f"{path}.tmp.{os.getpid()}_{int(time.time() * 1000)}"
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        for attempt in range(5):
            try:
                os.replace(temp_path, path)
                return
            except PermissionError:
                time.sleep(0.05 * (attempt + 1))
        # Final attempt — let it raise if still failing
        os.replace(temp_path, path)


def get_preferences():
    return load_json(USER_PREFS_PATH, default={})

def set_preference(key, value):
    prefs = get_preferences()
    prefs[key] = value
    save_json(USER_PREFS_PATH, prefs)

def get_assistant_context():
    return load_json(ASSISTANT_CONTEXT_PATH, default={})

def log_assistant_action(action, meta=None):
    ctx = get_assistant_context()
    if 'history' not in ctx:
        ctx['history'] = []
    entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'action': action,
        'meta': meta or {}
    }
    ctx['history'].append(entry)
    save_json(ASSISTANT_CONTEXT_PATH, ctx)

def get_history(limit=50):
    ctx = get_assistant_context()
    return ctx.get('history', [])[-limit:]

# --- Feature Learning (self-modifying feature registry) ---
FEATURE_REGISTRY_PATH = os.path.join(os.path.dirname(__file__), '..', 'feature_registry.json')

def enable_feature(feature):
    reg = load_json(FEATURE_REGISTRY_PATH, default={})
    reg[feature] = True
    save_json(FEATURE_REGISTRY_PATH, reg)

def disable_feature(feature):
    reg = load_json(FEATURE_REGISTRY_PATH, default={})
    reg[feature] = False
    save_json(FEATURE_REGISTRY_PATH, reg)

def get_enabled_features():
    reg = load_json(FEATURE_REGISTRY_PATH, default={})
    return [k for k, v in reg.items() if v]

# --- Task Logs and Frequent Workflows ---
def log_task(task, meta=None):
    log = load_json(TASK_LOG_PATH, default=[])
    entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'task': task,
        'meta': meta or {}
    }
    log.append(entry)
    save_json(TASK_LOG_PATH, log)

def get_task_log(limit=50):
    log = load_json(TASK_LOG_PATH, default=[])
    return log[-limit:]

def get_frequent_tasks(top_n=5):
    log = load_json(TASK_LOG_PATH, default=[])
    from collections import Counter
    counter = Counter(entry['task'] for entry in log)
    return counter.most_common(top_n)

# --- Natural-language Feature Learning ---
def learn_from_nl_instruction(instruction):
    """
    Parse a natural language instruction and update preferences or feature registry.
    Example: "Always summarize EOD" -> set_preference('summarize_eod', True)
    """
    instr = instruction.lower()
    if 'always summarize eod' in instr:
        set_preference('summarize_eod', True)
        enable_feature('summarize')
        return 'Preference set: always summarize EOD.'
    if 'disable' in instr and 'summarize' in instr:
        set_preference('summarize_eod', False)
        disable_feature('summarize')
        return 'Preference set: do not summarize EOD.'
    # Add more NL patterns as needed
    return 'Instruction not recognized.'

# Structure, style, and preferences memory
class StructureStyleMemory:
    def __init__(self, path=NOTE_STRUCTURE_MEMORY_PATH):
        self.path = path
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Ensure all keys exist
                if "structure" not in data:
                    data["structure"] = {}
                if "style" not in data:
                    data["style"] = {}
                if "preferences" not in data:
                    data["preferences"] = {}
                return data
        return {"structure": {}, "style": {}, "preferences": {}}

    def save(self):
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2)

    def remember_structure(self, note_id, structure):
        self.data["structure"][note_id] = structure
        self.save()

    def remember_style(self, note_id, style):
        self.data["style"][note_id] = style
        self.save()

    def set_preference(self, key, value):
        self.data["preferences"][key] = value
        self.save()

    def get_preference(self, key, default=None):
        return self.data["preferences"].get(key, default)

# Task, file, project, and feature memory
class AssistantTaskMemory:
    def __init__(self, path=os.path.join(os.path.dirname(__file__), '..', 'memory', 'task_log.json')):
        self.path = path
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"tasks": [], "files": [], "projects": [], "features": []}

    def save(self):
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2)

    def log_task(self, task):
        self.data["tasks"].append(task)
        self.save()

    def log_file(self, file):
        self.data["files"].append(file)
        self.save()

    def log_project(self, project):
        self.data["projects"].append(project)
        self.save()

    def log_feature(self, feature):
        self.data["features"].append(feature)
        self.save()

def suspend_all_models():
    """Suspend all LLM model processes (Ollama, llama.cpp, etc.) for gaming mode."""
    # Example: suspend ollama and llama.cpp processes
    for proc in psutil.process_iter(['name', 'cmdline']):
        try:
            if 'ollama' in proc.info['name'].lower() or 'llama' in ' '.join(proc.info['cmdline']).lower():
                proc.suspend()
        except Exception:
            pass

def resume_all_models():
    """Resume all LLM model processes after gaming mode."""
    for proc in psutil.process_iter(['name', 'cmdline']):
        try:
            if 'ollama' in proc.info['name'].lower() or 'llama' in ' '.join(proc.info['cmdline']).lower():
                proc.resume()
        except Exception:
            pass

def set_silent_mode(enable=True):
    """Set silent mode (mute notifications, TTS, etc.) for gaming mode."""
    prefs = get_preferences()
    prefs['silent_mode'] = bool(enable)
    save_json(USER_PREFS_PATH, prefs)

def enforce_low_power_mode():
    """Force only TinyLlama model and disable all background operations."""
    prefs = get_preferences()
    prefs['llm_model'] = 'tinyllama'
    prefs['background_ops'] = False
    save_json(USER_PREFS_PATH, prefs)
    # Optionally, stop background threads/processes here if running

def restore_normal_mode():
    """Restore normal model and background operation settings."""
    prefs = get_preferences()
    if 'llm_model' in prefs:
        del prefs['llm_model']
    prefs['background_ops'] = True
    if 'silent_mode' in prefs:
        del prefs['silent_mode']
    save_json(USER_PREFS_PATH, prefs)

def set_mode(mode):
    """Set the current assistant mode (default, gaming, low-power, study, creative, focus)."""
    prefs = get_preferences()
    prefs['mode'] = mode
    save_json(USER_PREFS_PATH, prefs)
    # Mode-specific actions
    if mode == 'gaming':
        suspend_all_models()
        set_silent_mode(True)
    elif mode == 'low-power':
        enforce_low_power_mode()
    elif mode == 'default':
        resume_all_models()
        restore_normal_mode()
    elif mode == 'study':
        # Focus on notes, calendar, polish
        enable_feature('summarize')
        enable_feature('note_polish')
        enable_feature('context_note')
        enable_feature('refactor')
        prefs['calendar_enabled'] = True
        # Disable creative/heavy features
        disable_feature('image_gen')
        disable_feature('audio_gen')
        disable_feature('creative_tools')
        prefs['background_ops'] = False
        save_json(USER_PREFS_PATH, prefs)
    elif mode == 'creative':
        # Enable creative/image/audio/gen tools
        enable_feature('image_gen')
        enable_feature('audio_gen')
        enable_feature('creative_tools')
        prefs['distraction_block'] = True
        # Optionally disable polish/refactor for focus
        disable_feature('note_polish')
        disable_feature('refactor')
        save_json(USER_PREFS_PATH, prefs)

def get_mode():
    prefs = get_preferences()
    return prefs.get('mode', 'default')

# --- File Safety & Approval System ---
def request_file_action(action, file_path, new_content=None):
    """Request approval for a file action (create, modify, delete). Returns True if approved, False otherwise."""
    queue = load_json(APPROVAL_QUEUE_PATH, default=[])
    entry = {
        'action': action,
        'file_path': file_path,
        'timestamp': datetime.utcnow().isoformat(),
        'new_content': new_content
    }
    queue.append(entry)
    save_json(APPROVAL_QUEUE_PATH, queue)
    print(f"[APPROVAL] {action.upper()} requested for {file_path}. Use 'jarvis approve' to review and approve.")
    return False  # Block until approved

def get_approval_queue():
    return load_json(APPROVAL_QUEUE_PATH, default=[])

def approve_next_action():
    queue = get_approval_queue()
    if not queue:
        print("No pending approvals.")
        return None
    entry = queue.pop(0)
    save_json(APPROVAL_QUEUE_PATH, queue)
    print(f"[APPROVED] {entry['action'].upper()} for {entry['file_path']}")
    return entry

def execute_approved_action(entry):
    """Execute an already-approved queue entry without re-requesting approval."""
    if not entry:
        return False
    action = entry.get('action')
    file_path = entry.get('file_path')
    if action in ('create', 'modify'):
        return safe_write_file(file_path, entry.get('new_content', ''), approved=True)
    if action == 'delete':
        return safe_delete_file(file_path, approved=True)
    if action == 'create_skill':
        from modules.skill_engine import register_approved_skill
        return register_approved_skill(entry.get('new_content'))
    print(f"[ERROR] Unknown approved action: {action}")
    return False


def preview_diff(file_path, new_content):
    """Show a diff between the current file and new content."""
    if not os.path.exists(file_path):
        print("[DIFF] File does not exist. (Create)")
        return
    with open(file_path, 'r', encoding='utf-8') as f:
        old = f.readlines()
    new = new_content.splitlines(keepends=True)
    diff = difflib.unified_diff(old, new, fromfile='old', tofile='new')
    print(''.join(diff))

def set_dry_run_mode(enable=True):
    prefs = get_preferences()
    prefs[DRY_RUN_PREF_KEY] = bool(enable)
    save_json(USER_PREFS_PATH, prefs)

def is_dry_run():
    prefs = get_preferences()
    return prefs.get(DRY_RUN_PREF_KEY, False)

import tempfile

def is_path_allowed(file_path):
    """Verify that file_path stays inside the project workspace, vault, or system temp directory."""
    try:
        # Block empty paths
        if not file_path or not file_path.strip():
            return False
        # Block null byte injection
        if '\x00' in file_path:
            return False
        abs_target = os.path.realpath(file_path)
        allowed_roots = [
            os.path.realpath(os.path.join(os.path.dirname(__file__), '..')),
            os.path.realpath(tempfile.gettempdir())
        ]
        try:
            cfg_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
            if os.path.exists(cfg_path):
                with open(cfg_path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                    vault = cfg.get('obsidian_vault_path')
                    if vault:
                        allowed_roots.append(os.path.realpath(vault))
        except Exception:
            pass

        for root in allowed_roots:
            try:
                if os.path.commonpath([abs_target, root]) == root:
                    return True
            except ValueError:
                continue
        return False
    except Exception:
        return False

# --- File operation wrappers ---
def safe_write_file(file_path, content, approved=False):
    if not is_path_allowed(file_path):
        print(f"[SECURITY WARNING] File write blocked outside allowed directories: {file_path}")
        return False
    if is_dry_run():
        print(f"[DRY RUN] Would write to {file_path}")
        preview_diff(file_path, content)
        return False
    if not approved and not request_file_action('modify' if os.path.exists(file_path) else 'create', file_path, content):
        preview_diff(file_path, content)
        print("[WAITING FOR APPROVAL]")
        return False
    parent = os.path.dirname(file_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    return True

def safe_delete_file(file_path, approved=False):
    if not is_path_allowed(file_path):
        print(f"[SECURITY WARNING] File delete blocked outside allowed directories: {file_path}")
        return False
    if is_dry_run():
        print(f"[DRY RUN] Would delete {file_path}")
        return False
    if not approved and not request_file_action('delete', file_path):
        print("[WAITING FOR APPROVAL]")
        return False
    if not os.path.exists(file_path):
        print(f"[WARNING] File not found, cannot delete: {file_path}")
        return False
    os.remove(file_path)
    return True


# Daemon/background process logic moved to modules/daemon_control.py
# CLI feature management moved to modules/feature_manager.py
# Import in main.py as needed
