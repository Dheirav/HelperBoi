"""Tests for the Windows/Linux seam in modules/platform_compat.py.

Run: .venv/bin/python -m unittest test_platform_compat -v

The pure functions are tested with the platform flags patched, so they pass on
any machine. The last class talks to Windows through WSL and is skipped
elsewhere, because a mock there would only prove the mock.
"""

import os
import shutil
import tempfile
import unittest
import wave
import unittest.mock
from unittest.mock import patch

from modules import platform_compat as pc


def as_wsl():
    return patch.multiple(pc, IS_WSL=True, IS_WINDOWS=False)


class PathTranslation(unittest.TestCase):
    def setUp(self):
        p = patch.object(pc, "_automount_root", return_value="/mnt")
        p.start()
        self.addCleanup(p.stop)

    def test_drive_paths_become_mnt_paths(self):
        with as_wsl():
            self.assertEqual(pc.to_linux_path("C:/Users/me/vault"), "/mnt/c/Users/me/vault")
            self.assertEqual(pc.to_linux_path("D:\\Notes\\a b"), "/mnt/d/Notes/a b")
            self.assertEqual(pc.to_linux_path("c:\\"), "/mnt/c")
            self.assertEqual(pc.to_linux_path("C:"), "/mnt/c")

    def test_other_paths_are_left_alone(self):
        with as_wsl():
            for p in ["/home/me/x", "relative/dir", "", None, "https://a.b/c", "tg://resolve"]:
                self.assertEqual(pc.to_linux_path(p), p)

    def test_custom_automount_root(self):
        with as_wsl(), patch.object(pc, "_automount_root", return_value="/win"):
            self.assertEqual(pc.to_linux_path("C:/x"), "/win/c/x")

    def test_plain_linux_does_not_rewrite(self):
        # A drive path on plain Linux is a mistake worth seeing, not hiding.
        with patch.multiple(pc, IS_WSL=False, IS_WINDOWS=False):
            self.assertEqual(pc.to_linux_path("C:/x"), "C:/x")


class WindowsStyleInput(unittest.TestCase):
    """The path guard must see Windows-style input as the path it names."""

    def test_backslashes_are_separators_off_windows(self):
        with as_wsl():
            self.assertEqual(pc.normalize_path("a\\b\\c.txt"), "a/b/c.txt")
            self.assertEqual(pc.normalize_path("..\\..\\x"), "../../x")

    def test_unc_is_refused_and_drive_depends_on_wsl(self):
        with as_wsl():
            self.assertTrue(pc.is_foreign_path("\\\\server\\share"))
            self.assertFalse(pc.is_foreign_path("C:\\Users"))  # translatable on WSL
        with patch.multiple(pc, IS_WSL=False, IS_WINDOWS=False):
            self.assertTrue(pc.is_foreign_path("Z:\\x"))  # plain Linux has no Z:

    def test_nothing_changes_on_windows(self):
        with patch.multiple(pc, IS_WSL=False, IS_WINDOWS=True):
            self.assertEqual(pc.normalize_path("C:\\x\\y"), "C:\\x\\y")
            self.assertFalse(pc.is_foreign_path("\\\\server\\share"))

    def test_guarded_write_lands_where_the_guard_looked(self):
        from modules.memory import safe_write_file, is_path_allowed
        root = os.path.dirname(os.path.abspath(__file__))
        win_style = "_pc_test_dir\\note.txt"
        target = os.path.join(root, "_pc_test_dir", "note.txt")
        stray = os.path.join(root, win_style)
        try:
            self.assertTrue(is_path_allowed(win_style))
            self.assertTrue(safe_write_file(win_style, "hello", approved=True))
            self.assertTrue(os.path.isfile(target))
            self.assertFalse(os.path.exists(stray), "a file with a backslash in its name was created")
        finally:
            shutil.rmtree(os.path.join(root, "_pc_test_dir"), ignore_errors=True)
            if os.path.exists(stray):
                os.remove(stray)

    def test_config_vault_path_is_allowed_after_translation(self):
        from modules import memory
        with as_wsl(), patch.object(pc, "_automount_root", return_value="/mnt"), \
                patch.object(memory.os.path, "exists", return_value=True), \
                patch("builtins.open", unittest.mock.mock_open(
                    read_data='{"obsidian_vault_path": "C:/Users/me/vault"}')):
            # realpath of a path that does not exist keeps the /mnt/c prefix.
            self.assertTrue(memory.is_path_allowed("C:\\Users\\me\\vault\\note.md"))


class OpenTarget(unittest.TestCase):
    def _run(self, target, *, which):
        with as_wsl(), patch.object(pc.shutil, "which", side_effect=which), \
                patch.object(pc, "to_windows_path", side_effect=lambda p: f"WIN({p})"), \
                patch.object(pc.subprocess, "Popen") as popen:
            pc.open_target(target)
            return popen.call_args[0][0] if popen.called else None

    def test_uri_goes_to_explorer_untouched(self):
        cmd = self._run("whatsapp://", which=lambda n: "/x/" + n)
        self.assertEqual(cmd, ["explorer.exe", "whatsapp://"])

    def test_https_url_is_a_uri_not_a_path(self):
        cmd = self._run("https://www.google.com/search?q=a&b=c", which=lambda n: "/x/" + n)
        self.assertEqual(cmd[1], "https://www.google.com/search?q=a&b=c")

    def test_drive_path_is_translated_for_windows(self):
        cmd = self._run("C:/Users/me", which=lambda n: "/x/" + n)
        self.assertEqual(cmd, ["explorer.exe", "WIN(/mnt/c/Users/me)"])

    def test_falls_back_to_xdg_open(self):
        cmd = self._run("/tmp/a.txt", which=lambda n: "/usr/bin/xdg-open" if n == "xdg-open" else None)
        self.assertEqual(cmd, ["/usr/bin/xdg-open", "/tmp/a.txt"])

    def test_raises_when_nothing_can_open_it(self):
        with as_wsl(), patch.object(pc.shutil, "which", return_value=None):
            with self.assertRaises(FileNotFoundError):
                pc.open_target("whatsapp://")


class OllamaEndpoint(unittest.TestCase):
    def check(self, env, expected):
        with patch.dict(os.environ, {"OLLAMA_HOST": env} if env is not None else {}, clear=False):
            if env is None:
                os.environ.pop("OLLAMA_HOST", None)
            self.assertEqual(pc.ollama_endpoint(), expected)

    def test_default_is_unchanged(self):
        self.check(None, "http://localhost:11434")
        self.check("", "http://localhost:11434")

    def test_forms_ollama_accepts(self):
        self.check("192.168.1.5:9999", "http://192.168.1.5:9999")
        self.check("myhost", "http://myhost:11434")
        self.check("https://example.com:443/", "https://example.com:443")

    def test_bind_address_becomes_loopback(self):
        self.check("0.0.0.0", "http://127.0.0.1:11434")
        self.check("0.0.0.0:11500", "http://127.0.0.1:11500")


class DaemonWithoutRegistry(unittest.TestCase):
    """What system_daemon does when there is no winreg, i.e. under WSL."""

    def setUp(self):
        from modules import system_daemon
        self.sd = system_daemon
        p = patch.object(system_daemon, "winreg", None)
        p.start()
        self.addCleanup(p.stop)

    def test_autostart_says_it_is_unavailable(self):
        for fn in (self.sd.enable_windows_autostart, self.sd.disable_windows_autostart):
            ok, msg = fn()
            self.assertFalse(ok)
            self.assertIn("registry", msg)
        self.assertEqual(self.sd.is_autostart_enabled(), (False, None))

    def test_keep_alive_is_reported_as_session_only(self):
        with patch.dict(os.environ, {}, clear=False):
            ok, msg = self.sd.enforce_vram_auto_unload("2m")
            self.assertTrue(ok)
            self.assertIn("this session only", msg)
            self.assertEqual(os.environ["OLLAMA_KEEP_ALIVE"], "2m")

    def test_status_still_reports(self):
        st = self.sd.get_system_status()
        self.assertFalse(st["autostart_enabled"])
        self.assertIn("ram_total_gb", st)


@unittest.skipUnless(pc.IS_WSL and shutil.which("powershell.exe") and shutil.which("reg.exe"),
                     "needs WSL with Windows interop")
class RealWindowsFromWSL(unittest.TestCase):
    def test_registered_and_unregistered_schemes(self):
        self.assertTrue(pc.windows_uri_registered("https://"))
        self.assertFalse(pc.windows_uri_registered("no-such-scheme-xyz://"))

    def test_scheme_name_cannot_inject_arguments(self):
        self.assertFalse(pc.windows_uri_registered("http /f"))
        self.assertFalse(pc.windows_uri_registered('a"; calc'))

    def test_windows_home_is_a_real_linux_path(self):
        home = pc.windows_home()
        self.assertTrue(home and os.path.isdir(home), home)

    def test_windows_voice_writes_a_wav_without_playing_it(self):
        text = "Jarvis speech check. It's got quotes, \"double\" ones too, and an accent: café."
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "say.wav")
            self.assertTrue(pc.speak_with_windows_voice(text, output_wav=out))
            with wave.open(out) as w:
                seconds = w.getnframes() / w.getframerate()
            # Eleven words of speech cannot be shorter than a second.
            self.assertGreater(seconds, 1.0)


if __name__ == "__main__":
    unittest.main()
