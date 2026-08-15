import os
import json
import threading
import time
from datetime import datetime

MEMORY_DIR = os.path.join(os.path.dirname(__file__), '..', 'memory')

daemon_thread = None
_daemon_running = False

def _daemon_loop():
    global _daemon_running
    while _daemon_running:
        # Example: status reporting, can be extended
        with open(os.path.join(MEMORY_DIR, 'daemon_status.json'), 'w', encoding='utf-8') as f:
            json.dump({'status': 'running', 'timestamp': datetime.utcnow().isoformat()}, f)
        time.sleep(10)  # Report status every 10 seconds

def start_daemon():
    """Start the background daemon for status reporting."""
    global daemon_thread, _daemon_running
    if daemon_thread and daemon_thread.is_alive():
        print("[DAEMON] Already running.")
        return
    _daemon_running = True
    daemon_thread = threading.Thread(target=_daemon_loop, daemon=True)
    daemon_thread.start()
    print("[DAEMON] Started.")

def stop_daemon():
    """Stop the background daemon."""
    global _daemon_running
    _daemon_running = False
    print("[DAEMON] Stopped.")

def get_daemon_status():
    status_path = os.path.join(MEMORY_DIR, 'daemon_status.json')
    if os.path.exists(status_path):
        with open(status_path, 'r', encoding='utf-8') as f:
            status = json.load(f)
        print(f"[DAEMON STATUS] {status}")
        return status
    print("[DAEMON STATUS] Not running.")
    return {'status': 'not running'}
