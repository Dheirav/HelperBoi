"""
New Tools Extension Module for HelperBoi / Jarvis
Provides:
- read_file: Safely view file contents
- write_file: Safely write content to a file with workspace path enforcement
- python_repl: Evaluate Python expressions and logic safely
- system_diagnose: Diagnostic audit of Ollama, VRAM, RAM, CPU, Vault & Git status
"""

import os
import sys
import io
import re
import json
import subprocess
from modules.memory import is_path_allowed, safe_write_file

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def configured_vault_path():
    """Resolve the Obsidian vault from config.json or OBSIDIAN_VAULT_PATH.

    Returns "" when neither is set. Callers should treat that as "no vault
    configured" rather than falling back to a hard-coded location, since the
    vault lives somewhere different on every machine.
    """
    env_path = os.environ.get("OBSIDIAN_VAULT_PATH")
    if env_path:
        return env_path
    config_file = os.path.join(PROJECT_ROOT, "config.json")
    try:
        with open(config_file) as f:
            return json.load(f).get("obsidian_vault_path") or ""
    except (OSError, ValueError):
        return ""


def read_file(file_path):
    """Safely read the content of a file within allowed paths."""
    file_path = str(file_path).strip()
    if not is_path_allowed(file_path):
        return f"[SECURITY ERROR] File path '{file_path}' is outside allowed directories!"
    if not os.path.exists(file_path):
        return f"[ERROR] File '{file_path}' does not exist!"
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(5000)
            return content if content else "(File is empty)"
    except Exception as e:
        return f"[ERROR] Failed to read file: {e}"


def write_file(file_path, content=""):
    """Safely write content to a file with path validation."""
    file_path = str(file_path).strip()
    if not is_path_allowed(file_path):
        return f"[SECURITY ERROR] Write target '{file_path}' is outside allowed directories!"
    try:
        ok = safe_write_file(file_path, content, approved=True)
        if ok or os.path.exists(file_path):
            return f"[SUCCESS] File written to '{file_path}'."
        return f"[NOTICE] File write requested for '{file_path}' (Approval Queue)."
    except Exception as e:
        return f"[ERROR] Failed to write file: {e}"


def python_repl(code_str):
    """Safely evaluate Python code string and capture result or output."""
    code_str = str(code_str).strip()
    if not code_str:
        return "(No python code provided)"

    # Remove markdown code fences if present
    if code_str.startswith("```"):
        lines = code_str.splitlines()
        if len(lines) > 2:
            code_str = "\n".join(lines[1:-1])

    old_stdout = sys.stdout
    redirected_output = io.StringIO()
    sys.stdout = redirected_output

    safe_globals = {
        "__builtins__": {
            "abs": abs, "all": all, "any": any, "bin": bin, "bool": bool,
            "chr": chr, "dict": dict, "dir": dir, "divmod": divmod, "enumerate": enumerate,
            "filter": filter, "float": float, "format": format, "frozenset": frozenset,
            "hex": hex, "int": int, "isinstance": isinstance, "issubclass": issubclass,
            "len": len, "list": list, "map": map, "max": max, "min": min, "oct": oct,
            "ord": ord, "pow": pow, "print": print, "range": range, "repr": repr,
            "reversed": reversed, "round": round, "set": set, "slice": slice,
            "sorted": sorted, "str": str, "sum": sum, "tuple": tuple, "zip": zip
        }
    }

    try:
        # Try evaluating as single expression first if no newlines
        if "\n" not in code_str and not code_str.startswith("print"):
            try:
                res = eval(code_str, safe_globals)
                if res is not None:
                    return str(res)
            except Exception:
                pass

        exec(code_str, safe_globals)
        output = redirected_output.getvalue().strip()
        return output if output else "[SUCCESS] Code executed."
    except Exception as e:
        return f"[PYTHON REPL ERROR]: {e}"
    finally:
        sys.stdout = old_stdout


def system_diagnose(vault_path=None):
    """Run full system diagnostics on Ollama, hardware, vault, and git status."""
    from modules.system_daemon import get_system_status
    st = get_system_status()

    ollama_ok = False
    models = []
    try:
        import requests
        resp = requests.get("http://localhost:11434/api/tags", timeout=2)
        if resp.status_code == 200:
            ollama_ok = True
            models = [m.get("name") for m in resp.json().get("models", [])]
    except Exception:
        pass

    vault_info = "Not configured"
    vault_notes_count = 0
    if vault_path and os.path.exists(vault_path):
        notes = [f for f in os.listdir(vault_path) if f.endswith('.md')]
        vault_notes_count = len(notes)
        vault_info = f"{vault_path} ({vault_notes_count} notes)"

    report = (
        "[SYSTEM DIAGNOSTICS REPORT]\n"
        f"• CPU Usage: {st['cpu_usage_percent']}%\n"
        f"• RAM: {st['ram_used_gb']} GB / {st['ram_total_gb']} GB\n"
        f"• GPU VRAM: {st['gpu_vram']}\n"
        f"• Ollama Server: {'ONLINE' if ollama_ok else 'OFFLINE'}\n"
        f"• Installed Models: {', '.join(models) if models else 'None'}\n"
        f"• Vault Status: {vault_info}\n"
        f"• Autostart Registry: {'ENABLED' if st['autostart_enabled'] else 'DISABLED'}\n"
        "------------------------------------"
    )
    return report


def find_windows_app_path(app_name):
    """Dynamically search Windows Registry App Paths for an executable."""
    import winreg
    clean_name = app_name.lower().replace(" ", "").replace(".exe", "")
    reg_keys = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths"
    ]
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for key_path in reg_keys:
            try:
                with winreg.OpenKey(root, key_path) as key:
                    num_subkeys, _, _ = winreg.QueryInfoKey(key)
                    for i in range(num_subkeys):
                        sub_name = winreg.EnumKey(key, i)
                        if clean_name in sub_name.lower():
                            with winreg.OpenKey(key, sub_name) as sub_key:
                                val, _ = winreg.QueryValueEx(sub_key, "")
                                if os.path.exists(val):
                                    return val
            except Exception:
                continue
    return None


def is_valid_win_uri(protocol_str):
    """Check if a URI scheme (e.g. 'whatsapp://') is registered in Windows Registry."""
    import winreg
    proto = protocol_str.replace("://", "").replace(":", "").strip().lower()
    if not proto:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, proto) as key:
            return True
    except Exception:
        return False


def open_app(app_name):
    """
    Launch a locally installed Windows application dynamically.
    Tries:
    1. Dynamic URI scheme (e.g. appname://) validated via Windows Registry
    2. PATH executable search (shutil.which)
    3. Windows Registry App Paths lookup
    4. Returns structured [CAPABILITY_GAP: open_app] if application cannot be located.
    """
    import shutil
    import subprocess
    import winreg

    app_name_raw = str(app_name).strip()
    app_name_str = app_name_raw.lower()
    clean_slug = re.sub(r'[^a-z0-9]', '', app_name_str)

    # 1. Dynamic & Known URI Schemes
    known_uris = {
        "whatsapp": "whatsapp://",
        "spotify": "spotify:",
        "discord": "discord://",
        "telegram": "tg://",
        "slack": "slack://",
        "zoom": "zoommtg://",
        "teams": "msteams://",
        "outlook": "ms-outlook://",
        "calculator": "calculator:",
        "settings": "ms-settings:",
        "store": "ms-windows-store:",
        "steam": "steam://"
    }
    uri_to_try = None
    for k, v in known_uris.items():
        if k in app_name_str:
            uri_to_try = v
            break
    if not uri_to_try and len(clean_slug) > 2:
        uri_to_try = f"{clean_slug}://"

    if uri_to_try and is_valid_win_uri(uri_to_try):
        try:
            os.startfile(uri_to_try)
            return f"[SUCCESS] Launched '{app_name_raw}' via URI scheme '{uri_to_try}'."
        except Exception:
            pass

    # 2. PATH search via shutil.which
    exe_name = app_name_str if app_name_str.endswith(".exe") else f"{app_name_str}.exe"
    found_cmd = shutil.which(app_name_str) or shutil.which(exe_name) or shutil.which(clean_slug)
    if found_cmd:
        try:
            subprocess.Popen([found_cmd], shell=True)
            return f"[SUCCESS] Launched '{found_cmd}'."
        except Exception as e:
            return f"[ERROR] Could not launch '{found_cmd}': {e}"

    # 3. Windows Registry App Paths Lookup
    reg_path = find_windows_app_path(clean_slug) or find_windows_app_path(app_name_str)
    if reg_path:
        try:
            os.startfile(reg_path)
            return f"[SUCCESS] Launched '{app_name_raw}' from registry path '{reg_path}'."
        except Exception as e:
            return f"[ERROR] Could not launch '{reg_path}': {e}"

    # 4. Capability Gap Failure - App could not be located!
    return (
        f"[CAPABILITY_GAP: open_app] Could not locate installed desktop app '{app_name_raw}'.\n"
        f"Jarvis could not find a Windows URI scheme, PATH executable, or Registry path for '{app_name_raw}'."
    )


def import_contacts_to_registry(file_path, vault_path=None):
    """
    Import Outlook CSV or vCard (.vcf) contacts file into Obsidian 'WhatsApp Registry.md'.
    Extracts names and phone numbers, formats them, and writes/appends to vault note.
    """
    import csv

    f_path = str(file_path).strip()
    if not os.path.exists(f_path):
        return f"[ERROR] File not found: {f_path}"

    contacts = []  # list of (name, phone)
    ext = os.path.splitext(f_path)[1].lower()

    if ext == ".csv":
        try:
            with open(f_path, "r", encoding="utf-8-sig", errors="ignore") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = (
                        row.get("Display Name")
                        or f"{row.get('First Name', '')} {row.get('Last Name', '')}".strip()
                        or row.get("Name")
                    )
                    phone = (
                        row.get("Mobile Phone")
                        or row.get("Primary Phone")
                        or row.get("Business Phone")
                        or row.get("Home Phone")
                        or row.get("Phone Number")
                        or row.get("Phone 1 - Value")
                    )
                    if name and phone:
                        clean_phone = re.sub(r"[^0-9+]", "", str(phone))
                        if len(clean_phone) >= 10:
                            contacts.append((name.strip(), clean_phone))
        except Exception as e:
            return f"[ERROR] Failed to parse CSV contacts file: {e}"

    elif ext == ".vcf":
        try:
            with open(f_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            cards = content.split("END:VCARD")
            for card in cards:
                fn_match = re.search(r"\nFN;?[^:]*:(.+)", card) or re.search(r"\nN;?[^:]*:(.+)", card)
                tel_match = re.search(r"\nTEL;?[^:]*:(.+)", card)
                if fn_match and tel_match:
                    raw_name = fn_match.group(1).replace(";", " ").strip()
                    raw_phone = tel_match.group(1).strip()
                    clean_phone = re.sub(r"[^0-9+]", "", raw_phone)
                    if raw_name and len(clean_phone) >= 10:
                        contacts.append((raw_name, clean_phone))
        except Exception as e:
            return f"[ERROR] Failed to parse vCard (.vcf) file: {e}"
    else:
        return f"[ERROR] Unsupported contact file format '{ext}'. Supported formats: .csv, .vcf"

    if not contacts:
        return f"[WARNING] No valid contacts with phone numbers found in '{f_path}'."

    # Write to Obsidian WhatsApp Registry.md
    target_vault = vault_path or configured_vault_path()
    if not target_vault:
        return (
            "[ERROR] No Obsidian vault configured. Set obsidian_vault_path in "
            "config.json or the OBSIDIAN_VAULT_PATH environment variable."
        )
    os.makedirs(target_vault, exist_ok=True)
    registry_file = os.path.join(target_vault, "WhatsApp Registry.md")

    existing_lines = []
    if os.path.exists(registry_file):
        with open(registry_file, "r", encoding="utf-8", errors="ignore") as f:
            existing_lines = f.readlines()

    with open(registry_file, "a", encoding="utf-8") as f:
        if not existing_lines:
            f.write("# WhatsApp Shortcuts Registry\n\n## Contacts\n")
        else:
            f.write("\n\n## Imported Contacts\n")

        for name, phone in contacts:
            f.write(f"- {name}: {phone}\n")

    return f"[SUCCESS] Imported {len(contacts)} contacts from '{f_path}' into '{registry_file}'!"


def sanitize_for_speech(text):
    """
    Format raw output strings into clean, human-like sentences suitable for Voice TTS.
    Strips raw code tags, long URLs, phone numbers, markdown fences, and file paths.
    """
    if not text:
        return ""

    clean = str(text)

    # Strip technical tags
    clean = re.sub(r'\[SUCCESS\]\s*', '', clean)
    clean = re.sub(r'\[ERROR\]\s*', '', clean)
    clean = re.sub(r'\[CAPABILITY_GAP:.*?\]\s*', '', clean)
    clean = re.sub(r'\[CAPABILITY LIMIT\]\s*', '', clean)

    # Clean raw URLs and schemes for speech
    clean = re.sub(r'https?://chat\.whatsapp\.com/\S+', 'the WhatsApp group link', clean)
    clean = re.sub(r'https?://\S+', 'the web link', clean)
    clean = re.sub(r'whatsapp://send\?phone=\S+', 'WhatsApp', clean)
    clean = re.sub(r'whatsapp://\S*', 'WhatsApp', clean)

    # Clean raw file paths for speech
    clean = re.sub(r'[A-Za-z]:\\[^:\s]+\.md', 'your notes', clean)
    clean = re.sub(r'[A-Za-z]:/[^:\s]+\.md', 'your notes', clean)

    # Clean markdown formatting symbols
    clean = re.sub(r'```.*?```', '', clean, flags=re.DOTALL)
    clean = re.sub(r'[`#*_]', '', clean)

    # Keep first 2 sentences for concise voice response
    lines = [l.strip() for l in clean.splitlines() if l.strip()]
    if len(lines) > 2:
        clean = ". ".join(lines[:2])
    else:
        clean = " ".join(lines)

    return clean.strip()


def lookup_whatsapp_registry(target_name, vault_path=None):
    """
    Search Obsidian notes and 'WhatsApp Registry.md' for phone numbers or group links.
    Uses exact substring matching, token word similarity, and difflib fuzzy matching.
    """
    import difflib

    clean_target = str(target_name).strip().lower()
    target_words = set(w for w in clean_target.split() if len(w) > 1)

    candidates = []  # list of (score, kind, value, display_name, file)

    search_paths = [vault_path, "./vaults", configured_vault_path()]
    for v_dir in search_paths:
        if not v_dir or not os.path.exists(v_dir):
            continue
        for root, _, files in os.walk(v_dir):
            for file in files:
                if file.endswith(".md"):
                    full_p = os.path.join(root, file)
                    try:
                        with open(full_p, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()

                        for line in content.splitlines():
                            line_str = line.strip()
                            if not line_str.startswith("-") and not line_str.startswith("*"):
                                continue

                            line_lower = line_str.lower()
                            disp_name = line_str.lstrip("-* ").split(":")[0].strip()
                            disp_lower = disp_name.lower()

                            # Fuzzy scoring
                            score = 0.0
                            if clean_target == disp_lower:
                                score = 1.0
                            elif clean_target in disp_lower:
                                score = 0.9
                            elif any(w in disp_lower for w in target_words):
                                score = 0.75
                            else:
                                score = difflib.SequenceMatcher(None, clean_target, disp_lower).ratio()

                            if score >= 0.5:
                                group_match = re.search(r'https://chat\.whatsapp\.com/[a-zA-Z0-9]+', line_str)
                                if group_match:
                                    candidates.append((score, "group_link", group_match.group(0), disp_name, file))
                                else:
                                    phone_match = re.search(r'\+?[0-9]{10,15}', line_str)
                                    if phone_match:
                                        candidates.append((score, "phone", phone_match.group(0), disp_name, file))
                    except Exception:
                        continue

    if not candidates:
        return (None, None, None, None)

    candidates.sort(key=lambda x: x[0], reverse=True)
    best_score, kind, val, disp_name, src = candidates[0]
    return (kind, val, src, disp_name)


def handle_in_app_action(app_name, sub_action, target):
    """
    Handle sub-actions within apps (e.g. 'open chat X in WhatsApp').
    Attempts deep-linking where supported. Returns honest capability notice if not possible.
    """
    app = str(app_name).strip().lower()
    action = str(sub_action).strip().lower()
    target_str = str(target).strip()

    # WhatsApp: supports phone numbers, group invite links, or vault group/contact shortcuts
    if app == "whatsapp":
        # 1. Direct Group Invite Link or Code
        if "chat.whatsapp.com" in target_str or (len(target_str) >= 20 and " " not in target_str and not target_str.isdigit()):
            clean_code = target_str.split("chat.whatsapp.com/")[-1].strip()
            group_link = f"https://chat.whatsapp.com/{clean_code}"
            try:
                os.startfile(group_link)
                return f"[SUCCESS] Opened WhatsApp group chat via link '{group_link}'."
            except Exception as e:
                return f"[ERROR] Failed to open WhatsApp group link: {e}"

        # 2. Check if target is a phone number
        phone = re.sub(r'[^0-9+]', '', target_str)
        if len(phone) >= 10:
            uri = f"whatsapp://send?phone={phone}"
            try:
                os.startfile(uri)
                return f"[SUCCESS] Opened WhatsApp chat with phone number {phone}."
            except Exception as e:
                return f"[ERROR] Failed to open WhatsApp deep link: {e}"

        # 3. Check Obsidian Vault Registry for contact or group shortcut
        kind, value, source_file, disp_name = lookup_whatsapp_registry(target_str)
        if kind == "group_link":
            try:
                os.startfile(value)
                return f"[SUCCESS] Found saved group link for '{disp_name or target_str}' in '{source_file}'! Opened group chat."
            except Exception as e:
                return f"[ERROR] Failed to open group link from registry: {e}"
        elif kind == "phone":
            clean_p = re.sub(r'[^0-9+]', '', value)
            uri = f"whatsapp://send?phone={clean_p}"
            try:
                os.startfile(uri)
                contact_label = disp_name if disp_name else target_str
                return f"[SUCCESS] Found contact '{contact_label}' ({clean_p}) in '{source_file}'! Opened WhatsApp chat."
            except Exception as e:
                return f"[ERROR] Failed to open WhatsApp chat for contact: {e}"

        # 4. Fallback: Launch WhatsApp app & explain Registry file feature
        try:
            os.startfile("whatsapp://")
        except Exception:
            pass
        return (
            f"[SUCCESS] Launched WhatsApp application.\n\n"
            f"[Tip: Create a 'WhatsApp Registry.md' Note in Obsidian]:\n"
            f"You can create a note in Obsidian with your contacts and group links:\n"
            f"- Niveditha: +917358114173\n"
            f"- Study Group: https://chat.whatsapp.com/XYZ123\n"
            f"Jarvis will automatically read your notes and open chats/groups directly by name!"
        )

    # Spotify: supports search deep-link
    if app == "spotify":
        if action in ("play", "search", "find", "open"):
            import urllib.parse
            uri = f"spotify:search:{urllib.parse.quote(target_str)}"
            try:
                os.startfile(uri)
                return f"[SUCCESS] Opened Spotify search for '{target_str}'."
            except Exception:
                return f"[CAPABILITY LIMIT] Could not deep-link into Spotify for '{target_str}'."

    # Obsidian: supports note deep-linking & vault search
    if app in ("obsidian", "obsidian note", "obsidian vault"):
        import urllib.parse
        clean_target = urllib.parse.quote(target_str)
        if action in ("search", "find"):
            uri = f"obsidian://search?vault=Obsidian&query={clean_target}"
            msg = f"[SUCCESS] Opened Obsidian vault search for '{target_str}'."
        else:
            uri = f"obsidian://open?vault=Obsidian&file={clean_target}"
            msg = f"[SUCCESS] Opened note '{target_str}' in Obsidian."
        try:
            os.startfile(uri)
            return msg
        except Exception:
            return f"[CAPABILITY LIMIT] Could not open Obsidian URI scheme for '{target_str}'."

    # YouTube: supports search & video deep-linking
    if app in ("youtube", "yt"):
        import urllib.parse
        search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(target_str)}"
        try:
            os.startfile(search_url)
            return f"[SUCCESS] Opened YouTube search for '{target_str}'."
        except Exception as e:
            return f"[ERROR] Could not open YouTube search: {e}"

    # Google Maps / Maps: supports search & directions
    if app in ("google maps", "maps", "googlemap", "navigation"):
        import urllib.parse
        encoded = urllib.parse.quote(target_str)
        if action in ("direction", "directions", "route", "navigate"):
            maps_url = f"https://www.google.com/maps/dir//{encoded}"
            msg = f"[SUCCESS] Opened Google Maps navigation route to '{target_str}'."
        else:
            maps_url = f"https://www.google.com/maps/search/{encoded}"
            msg = f"[SUCCESS] Opened Google Maps search for '{target_str}'."
        try:
            os.startfile(maps_url)
            return msg
        except Exception as e:
            return f"[ERROR] Could not open Google Maps: {e}"

    # VS Code / Visual Studio Code / Code
    if app in ("vscode", "vs code", "visual studio code", "code"):
        import urllib.parse
        target_path = target_str
        if os.path.exists(target_str):
            target_path = os.path.abspath(target_str)

        uri = f"vscode://file/{urllib.parse.quote(target_path)}"
        try:
            import subprocess
            subprocess.Popen(["code", target_path], shell=True)
            return f"[SUCCESS] Opened '{target_str}' in VS Code."
        except Exception:
            try:
                os.startfile(uri)
                return f"[SUCCESS] Opened '{target_str}' in VS Code."
            except Exception as e:
                return f"[ERROR] Could not launch VS Code: {e}"

    # Discord
    if app in ("discord", "dc"):
        try:
            os.startfile("discord://")
            return f"[SUCCESS] Opened Discord application."
        except Exception:
            return open_app("discord")

    # Notion
    if app in ("notion",):
        try:
            os.startfile("notion://")
            return f"[SUCCESS] Opened Notion application."
        except Exception:
            return open_app("notion")

    # File Explorer / Folders
    if app in ("explorer", "folder", "directory", "file explorer"):
        user_profile = os.environ.get("USERPROFILE") or os.path.expanduser("~")
        folder_map = {
            "downloads": os.path.join(user_profile, "Downloads"),
            "desktop": os.path.join(user_profile, "Desktop"),
            "documents": os.path.join(user_profile, "Documents"),
            "pictures": os.path.join(user_profile, "Pictures"),
            "videos": os.path.join(user_profile, "Videos"),
            "obsidian": configured_vault_path(),
            "helperboi": PROJECT_ROOT
        }
        clean_tgt = target_str.lower().strip()
        target_folder = folder_map.get(clean_tgt) or (target_str if os.path.exists(target_str) else None)
        if target_folder and os.path.exists(target_folder):
            try:
                os.startfile(target_folder)
                return f"[SUCCESS] Opened folder '{target_folder}' in File Explorer."
            except Exception as e:
                return f"[ERROR] Could not open folder: {e}"

    # Telegram: supports username deep-link
    if app == "telegram":
        clean_target = target_str.lstrip("@")
        uri = f"tg://resolve?domain={clean_target}"
        try:
            os.startfile(uri)
            return f"[SUCCESS] Opened Telegram chat with '@{clean_target}'."
        except Exception:
            return (
                f"[CAPABILITY LIMIT] I opened Telegram but could not navigate to '{target_str}'.\n"
                f"Provide the exact Telegram username (e.g. @username) for a direct link."
            )

    # Generic: try opening the app, but honestly report the sub-action gap
    app_result = open_app(app)
    if "[SUCCESS]" in app_result:
        return (
            f"{app_result}\n"
            f"[CAPABILITY LIMIT] I launched '{app}' but I cannot perform the specific action "
            f"'{action} {target_str}' inside the app. This app doesn't support deep-linking for that action."
        )
    return app_result



def open_browser(target="https://www.google.com"):
    """Open default web browser to a URL, specific web service, or search query."""

    import webbrowser
    import urllib.parse
    import re
    
    target_str = str(target).strip()
    target_lower = target_str.lower()

    # Pre-defined smart web shortcuts
    SHORTCUTS = {
        "gmail": "https://mail.google.com",
        "mail": "https://mail.google.com",
        "youtube": "https://www.youtube.com",
        "github": "https://github.com",
        "reddit": "https://www.reddit.com",
        "twitter": "https://x.com",
        "chatgpt": "https://chatgpt.com",
        "google": "https://www.google.com"
    }

    # 1. Check for specific site keywords in spoken phrase (e.g. gmail, youtube, github)
    urls_to_open = []
    for site, site_url in SHORTCUTS.items():
        if site in target_lower and site != "google":
            if site_url not in urls_to_open:
                urls_to_open.append(site_url)

    if urls_to_open:
        for url in urls_to_open:
            webbrowser.open(url)
        return f"[SUCCESS] Opened web browser to: {', '.join(urls_to_open)}"

    # 2. Direct URLs or domains
    if target_lower.startswith("http://") or target_lower.startswith("https://"):
        url = target_str
    elif "." in target_str and " " not in target_str:
        url = f"https://{target_str}"
    elif "google" in target_lower or "browser" in target_lower or not target_str:
        url = "https://www.google.com"
    else:
        # Strip common action prefixes ("can you search for", "look up", "find", "search")
        clean_query = re.sub(r"^(can you|please|could you)?\s*(open|search for|search|look up|find|go to)\s*", "", target_str, flags=re.I).strip()
        url = f"https://www.google.com/search?q={urllib.parse.quote(clean_query or target_str)}"

    try:
        webbrowser.open(url)
        return f"[SUCCESS] Opened web browser to {url}"
    except Exception as e:
        return f"[ERROR] Failed to open browser: {e}"


def handle_missing_tool_prompt(action_name="requested_action"):
    """Format clear user notification and choices when a requested tool/action is missing."""
    clean_action = str(action_name).strip()
    return (
        f"⚠️ [Missing Tool Notice]: I don't currently have a built-in tool for '{clean_action}'.\n\n"
        "How would you like to proceed?\n"
        "  1. Proceed with creating a custom Python skill/tool in skills/\n"
        "  2. Search/install an existing tested MCP server or plugin tool\n"
        "  3. Cancel\n\n"
        "Please select an option (1-3) or confirm your preference."
    )
