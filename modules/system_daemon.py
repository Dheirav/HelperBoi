"""
System Daemon & Resource Management Module for HelperBoi
Handles startup auto-run configuration, VRAM auto-unload, and hardware system status.

The auto-run entry lives in the Windows registry, so it only exists when Python
is running on Windows. Under WSL those calls report that plainly instead of
failing, and the rest (status, VRAM unload for this process) still works.
"""

import os
import sys
import logging
import subprocess
import psutil
from modules.platform_compat import winreg

logger = logging.getLogger("helperboi.system_daemon")

RUN_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "HelperBoiAssistant"

# Why a message and not a fake success: nothing here can start a Linux process
# at Windows login, so claiming autostart was enabled would be wrong. On WSL the
# working equivalent is a systemd user service (systemd is enabled in wsl.conf).
_NO_REGISTRY = (
    "Windows autostart needs the Windows registry, which Python under WSL/Linux "
    "cannot reach. Use a systemd user service instead."
)


def enforce_vram_auto_unload(keep_alive="5m"):
    """
    Set OLLAMA_KEEP_ALIVE environment variable for user session to automatically unload models from VRAM when idle.
    """
    try:
        os.environ["OLLAMA_KEEP_ALIVE"] = keep_alive
        if winreg is None:
            # Only this process and its children see the value. The Ollama server
            # reads its own environment, so a permanent change belongs where the
            # server is started (shell profile or its systemd unit).
            return True, (f"OLLAMA_KEEP_ALIVE={keep_alive} set for this session only. "
                          "Set it where the Ollama server starts to make it permanent.")
        # Set user environment variable in Windows registry
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "OLLAMA_KEEP_ALIVE", 0, winreg.REG_SZ, keep_alive)
        logger.info(f"OLLAMA_KEEP_ALIVE set to {keep_alive}")
        return True, f"OLLAMA_KEEP_ALIVE set to {keep_alive} (VRAM auto-unloads after {keep_alive} idle)."
    except Exception as e:
        logger.error(f"Failed to set OLLAMA_KEEP_ALIVE: {e}")
        return False, f"Failed to set VRAM auto-unload: {e}"


def enable_windows_autostart():
    """
    Add HelperBoi daemon startup entry to Windows Registry HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run.
    """
    if winreg is None:
        return False, _NO_REGISTRY
    try:
        python_exe = sys.executable
        main_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
        cmd_str = f'"{python_exe}" "{main_py}" --daemon'

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_REG_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd_str)

        enforce_vram_auto_unload("5m")
        return True, "HelperBoi enabled on Windows boot. VRAM auto-unload configured."
    except Exception as e:
        logger.error(f"Failed to enable Windows autostart: {e}")
        return False, f"Failed to enable Windows autostart: {e}"


def disable_windows_autostart():
    """
    Remove HelperBoi daemon startup entry from Windows Registry.
    """
    if winreg is None:
        return False, _NO_REGISTRY
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_REG_KEY, 0, winreg.KEY_SET_VALUE) as key:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
        return True, "HelperBoi disabled on Windows boot."
    except Exception as e:
        logger.error(f"Failed to disable Windows autostart: {e}")
        return False, f"Failed to disable Windows autostart: {e}"


def is_autostart_enabled():
    """Check if autostart registry entry exists."""
    if winreg is None:
        return False, None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_REG_KEY, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, APP_NAME)
            return True, val
    except FileNotFoundError:
        return False, None
    except Exception as e:
        return False, None


def get_system_status():
    """
    Retrieve CPU, RAM, GPU VRAM, and autostart status.
    """
    cpu_percent = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()

    gpu_info = "N/A"
    try:
        smi = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=3)
        if smi.returncode == 0 and smi.stdout.strip():
            parts = smi.stdout.strip().split(",")
            if len(parts) >= 3:
                gpu_info = f"Used {parts[0].strip()} MB / {parts[1].strip()} MB VRAM (GPU Util: {parts[2].strip()}%)"
    except Exception:
        pass

    autostart_on, auto_cmd = is_autostart_enabled()

    return {
        "cpu_usage_percent": cpu_percent,
        "ram_used_gb": round(ram.used / (1024**3), 2),
        "ram_total_gb": round(ram.total / (1024**3), 2),
        "gpu_vram": gpu_info,
        "autostart_enabled": autostart_on,
        "autostart_cmd": auto_cmd,
        "ollama_keep_alive": os.getenv("OLLAMA_KEEP_ALIVE", "Not Set")
    }
