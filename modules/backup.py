import subprocess
import os
from datetime import datetime

def backup_vault(vault_path=".", github_pat=None):
    if not os.path.exists(os.path.join(vault_path, ".git")):
        print("⚠️ No Git repo found in vault folder. Skipping backup.")
        return

    env = os.environ.copy()
    if github_pat:
        # Set up GIT_ASKPASS to provide the PAT for HTTPS authentication
        askpass_script = os.path.join(vault_path, "git_askpass_pat.sh")
        with open(askpass_script, "w") as f:
            f.write(f"#!/bin/sh\necho '{github_pat}'\n")
        os.chmod(askpass_script, 0o700)
        env["GIT_ASKPASS"] = askpass_script

    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        subprocess.run(["git", "-C", vault_path, "add", "."], check=True, env=env)
        commit_result = subprocess.run(
            ["git", "-C", vault_path, "commit", "-m", f"Jarvis Auto Backup - {timestamp}"],
            capture_output=True,
            text=True,
            env=env
        )

        if "nothing to commit" in commit_result.stdout.lower():
            print("🟡 Nothing new to back up. Vault is clean.")
        else:
            print("✅ Obsidian vault backed up.")
        subprocess.run(["git", "-C", vault_path, "push"], check=True, env=env)
        print("✅ Obsidian vault backed up.")
    except subprocess.CalledProcessError as e:
        print("❌ Backup failed:", e)
    finally:
        if github_pat:
            try:
                os.remove(askpass_script)
            except Exception:
                pass
