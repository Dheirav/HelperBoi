"""Where HelperBoi is running, and the few places Windows and Linux differ.

The assistant was written on Windows, so it called os.startfile, winreg and the
Windows speech engine directly. Under WSL none of those exist, and the first
import of winreg fails the whole program. Every platform-specific call now goes
through this file, which keeps the rest of the code neutral and gives one place
to read when something behaves differently on one side.

On WSL the Windows programs are still reachable (explorer.exe, cmd.exe,
powershell.exe, reg.exe sit on PATH), and that is how apps are launched and
text is spoken. Nothing here needs a Windows Python.
"""

import os
import platform
import re
import shutil
import subprocess
import tempfile
from functools import lru_cache

try:
    import winreg  # Windows only
except ImportError:
    winreg = None

IS_WINDOWS = os.name == "nt"


def _detect_wsl():
    if IS_WINDOWS:
        return False
    if os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP"):
        return True
    # Environment variables are dropped by some launchers (sudo, cron), the
    # kernel string is not.
    return "microsoft" in platform.release().lower()


IS_WSL = _detect_wsl()

# "C:\x", "c:/x" and bare "C:" are drive paths. A scheme of two or more letters
# ("tg:", "spotify:", "https:") is a URI, which is why the drive pattern is
# limited to a single letter.
_DRIVE = re.compile(r"^([A-Za-z]):(?:[\\/]+(.*))?$")
_URI = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]+:")


def _automount_root():
    """The folder WSL mounts Windows drives under (/mnt unless wsl.conf says otherwise)."""
    try:
        with open("/etc/wsl.conf", encoding="utf-8") as f:
            for line in f:
                m = re.match(r"\s*root\s*=\s*(\S+)", line)
                if m:
                    return m.group(1).rstrip("/") or "/"
    except OSError:
        pass
    return "/mnt"


def to_linux_path(path):
    """Turn a Windows drive path into the WSL one (C:/x -> /mnt/c/x).

    Anything else is returned unchanged, including on Windows and on plain
    Linux, where a drive path means nothing and rewriting it would hide the
    mistake instead of showing it.
    """
    if not path or IS_WINDOWS or not IS_WSL:
        return path
    m = _DRIVE.match(str(path).strip())
    if not m:
        return path
    rest = (m.group(2) or "").replace("\\", "/")
    return f"{_automount_root()}/{m.group(1).lower()}" + (f"/{rest}" if rest else "")


def normalize_path(path):
    """Read Windows-style input as the path it means on this OS.

    Users and LLMs write C:\\Users\\me\\notes or ..\\..\\x even when HelperBoi
    runs in WSL. On Linux a backslash is an ordinary filename character, so
    without this such a string is a single odd filename inside the current
    folder, and the path guard approved it while any Windows program handed the
    same string would act on a real system path. Unchanged on Windows.
    """
    if IS_WINDOWS or not path:
        return path
    return to_linux_path(str(path)).replace("\\", "/")


def is_foreign_path(path):
    """A Windows drive or UNC path this machine cannot translate.

    Plain Linux has no C: drive, so "Z:\\x" can only be a mistake or an attempt to
    slip past a check. UNC paths are refused everywhere off Windows, including
    WSL, because they name another machine.
    """
    if IS_WINDOWS or not path:
        return False
    s = str(path).strip()
    return s.startswith("\\\\") or (bool(_DRIVE.match(s)) and not IS_WSL)


def to_windows_path(path):
    """Path as a Windows program should see it (wslpath -w); unchanged if that fails."""
    if not IS_WSL:
        return path
    try:
        out = subprocess.run(["wslpath", "-w", str(path)], capture_output=True,
                             text=True, timeout=5)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return path


@lru_cache(maxsize=1)
def windows_home():
    """The Windows user's profile folder as a Linux path, or None off WSL.

    Downloads, Desktop and the like live there, not in the Linux home. cmd.exe
    is started in /mnt/c because from a Linux folder it prints a UNC-path
    warning on the same stream we read.
    """
    if IS_WINDOWS:
        return os.environ.get("USERPROFILE")
    if not IS_WSL:
        return None
    try:
        out = subprocess.run(["cmd.exe", "/c", "echo %USERPROFILE%"], capture_output=True,
                             text=True, timeout=8, cwd=f"{_automount_root()}/c")
        value = out.stdout.strip()
        if out.returncode == 0 and _DRIVE.match(value):
            return to_linux_path(value)
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def open_target(target):
    """Open a file, folder, URL or app URI with whatever the desktop uses.

    Replaces os.startfile, which exists only on Windows. On WSL the launcher is
    explorer.exe, which understands paths, URLs and registered schemes such as
    whatsapp://. Raises when no launcher exists so the caller can say so
    instead of reporting a launch that never happened.
    """
    t = str(target)
    if IS_WINDOWS:
        os.startfile(t)  # noqa: S606 (Windows only)
        return

    is_uri = bool(_URI.match(t)) and not _DRIVE.match(t)
    if IS_WSL and shutil.which("explorer.exe"):
        arg = t if is_uri else to_windows_path(to_linux_path(t))
        # explorer.exe returns 1 even when it worked, so the exit code is ignored.
        subprocess.Popen(["explorer.exe", arg], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        return
    opener = shutil.which("xdg-open")
    if opener:
        subprocess.Popen([opener, t], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    raise FileNotFoundError("no launcher found (explorer.exe on WSL, xdg-open on Linux)")


def windows_uri_registered(protocol):
    """Is a URI scheme (whatsapp, tg, ...) registered with Windows?

    From Windows this reads the registry directly. From WSL it asks reg.exe,
    because the registry is not visible to Linux.
    """
    proto = protocol.replace("://", "").replace(":", "").strip().lower()
    if not proto or not re.fullmatch(r"[a-z][a-z0-9+.\-]*", proto):
        return False
    if winreg is not None:
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, proto):
                return True
        except OSError:
            return False
    if IS_WSL and shutil.which("reg.exe"):
        try:
            out = subprocess.run(["reg.exe", "query", f"HKCR\\{proto}", "/ve"],
                                 capture_output=True, timeout=5)
            return out.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False
    return False


def speak_with_windows_voice(text, output_wav=None, timeout=60):
    """Speak text with the Windows SAPI voice from WSL; True on success.

    The text goes through a temp file read as UTF-8, not the command line,
    because quotes and non-ASCII characters do not survive the hop from Linux
    into PowerShell. With output_wav the speech is written to that file and
    nothing is played, which is how this is checked without making noise.
    """
    if not (IS_WSL and shutil.which("powershell.exe")):
        return False
    with tempfile.NamedTemporaryFile("w", suffix=".txt", encoding="utf-8", delete=False) as f:
        f.write(text)
        src = f.name
    try:
        sink = ""
        if output_wav:
            sink = f"$s.SetOutputToWaveFile('{to_windows_path(output_wav)}'); "
        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"{sink}$s.Speak((Get-Content -Raw -Encoding UTF8 -LiteralPath '{to_windows_path(src)}')); "
            "$s.Dispose()"
        )
        out = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                             capture_output=True, timeout=timeout)
        return out.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False
    finally:
        try:
            os.unlink(src)
        except OSError:
            pass


def ollama_endpoint():
    """Base URL of the Ollama server, honouring OLLAMA_HOST like the ollama CLI does.

    Accepts "host:port", "host" or a full URL. 0.0.0.0 is what a server binds
    to, not an address a client can call, so it becomes 127.0.0.1. Without the
    variable this is the same http://localhost:11434 the code used before.
    """
    raw = (os.environ.get("OLLAMA_HOST") or "").strip()
    if not raw:
        return "http://localhost:11434"
    if "://" not in raw:
        raw = "http://" + raw
    raw = raw.rstrip("/")
    if raw.startswith(("http://0.0.0.0", "https://0.0.0.0")):
        raw = raw.replace("0.0.0.0", "127.0.0.1", 1)
    if not re.search(r":\d+$", raw):
        raw += ":11434"
    return raw
