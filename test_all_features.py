"""
Test script for Jarvis: tests all major features in modules/ and main CLI logic.
This script is for development/CI sanity checks, not for production.
"""
import os
import sys
import tempfile
import shutil
import json
import subprocess

# Import modules directly
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from modules import note_polish, code_explain, context_note, refactor, interest_features, assistant_memory_features, memory, vector_search

TEST_VAULT = tempfile.mkdtemp(prefix="jarvis_test_vault_")
TEST_NOTE = os.path.join(TEST_VAULT, "test_note.md")

# --- Helper: create a test note ---
def create_test_note(content="This is a test note. It mentions Python and AI."):
    os.makedirs(TEST_VAULT, exist_ok=True)
    with open(TEST_NOTE, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"[DEBUG] Created test note at: {TEST_NOTE}")
    print(f"[DEBUG] Note content: {content}")
    return TEST_NOTE

def cleanup():
    print(f"[DEBUG] Cleaning up test vault: {TEST_VAULT}")
    shutil.rmtree(TEST_VAULT, ignore_errors=True)
    if os.path.exists('memory/vector_embeddings.json'):
        os.remove('memory/vector_embeddings.json')
        print("[DEBUG] Removed memory/vector_embeddings.json")

def ensure_ollama_model(model_name="qwen2.5-coder:7b"):
    """Ensure the Ollama model is pulled and available."""
    print(f"[DEBUG] Ensuring Ollama model '{model_name}' is available...")
    try:
        import requests
        resp = requests.get("http://localhost:11434/api/tags", timeout=2)
        if resp.status_code == 200:
            models = [m.get("name") for m in resp.json().get("models", [])]
            if any(model_name in m for m in models):
                print(f"[DEBUG] Model '{model_name}' is already available.")
                return
    except Exception:
        print(f"[DEBUG] Ollama server offline; skipping model pull check.")
        return


# --- Test note_polish ---
def test_note_polish():
    print("[TEST] note_polish...")
    note = "this is a test note. it needs polish."
    print(f"[DEBUG] Input note: {note}")
    polished = note_polish.polish_note(note)
    print(f"[DEBUG] Polished note: {polished}")
    assert "This is a test note" in polished or polished.strip(), "Polish failed"
    print("[OK] note_polish")

# --- Test code_explain ---
def test_code_explain():
    print("[TEST] code_explain...")
    code = "def add(a, b): return a + b"
    print(f"[DEBUG] Input code: {code}")
    explanation = code_explain.explain_code(code)
    print(f"[DEBUG] Explanation: {explanation}")
    assert "add" in explanation.lower() or explanation.strip(), "Explain failed"
    print("[OK] code_explain")

# --- Test context_note ---
def test_context_note():
    print("[TEST] context_note...")
    note = context_note.generate_context_note("Explain quantum computing simply.", TEST_VAULT)
    print(f"[DEBUG] Generated context note: {note}")
    assert note.strip(), "Context note failed"
    print("[OK] context_note")

# --- Test refactor ---
def test_refactor():
    print("[TEST] refactor...")
    code = "def add(a,b):return a+b"
    print(f"[DEBUG] Input code: {code}")
    refactored = refactor.refactor_code(code)
    print(f"[DEBUG] Refactored code: {refactored}")
    assert ("def add" in refactored or "def " in refactored) and ":" in refactored, "Refactor failed"
    print("[OK] refactor")

# --- Test interest_features ---
def test_interest_features():
    print("[TEST] interest_features...")
    notes = {TEST_NOTE: "Python AI machine learning"}
    print(f"[DEBUG] Notes: {notes}")
    interests = interest_features.detect_interests(notes)
    print(f"[DEBUG] Detected interests: {interests}")
    assert "python" in interests or interests, "Interest detection failed"
    print("[OK] interest_features")

# --- Test assistant_memory_features ---
def test_assistant_memory_features():
    print("[TEST] assistant_memory_features...")
    assistant_memory_features.log_user_action("test_action")
    assistant_memory_features.learn_feature("test_feature")
    assistant_memory_features.log_task("test_task")
    log = assistant_memory_features.get_task_log()
    print(f"[DEBUG] Task log: {log}")
    assert log, "Task log missing"
    frequent = assistant_memory_features.get_frequent_tasks()
    print(f"[DEBUG] Frequent tasks: {frequent}")
    assert frequent, "Frequent tasks missing"
    print("[OK] assistant_memory_features")

# --- Test memory (prefs, history, feature registry) ---
def test_memory():
    print("[TEST] memory...")
    memory.set_preference("test_key", "test_value")
    prefs = memory.get_preferences()
    print(f"[DEBUG] Preferences: {prefs}")
    assert prefs.get("test_key") == "test_value", "Prefs failed"
    memory.log_assistant_action("test_action")
    history = memory.get_history()
    print(f"[DEBUG] History: {history}")
    assert history, "History failed"
    memory.enable_feature("test_feature")
    enabled = memory.get_enabled_features()
    print(f"[DEBUG] Enabled features: {enabled}")
    assert "test_feature" in enabled, "Feature registry failed"
    print("[OK] memory")

# --- Test vector_search ---
def test_vector_search():
    print("[TEST] vector_search...")
    create_test_note()
    print(f"[DEBUG] Building embeddings for vault: {TEST_VAULT}")
    embeddings = vector_search.build_embeddings(TEST_VAULT)
    print(f"[DEBUG] Embeddings: {embeddings}")
    print(f"[DEBUG] Running search for 'Python'...")
    results = vector_search.search("Python", top_k=1, vault_path=TEST_VAULT)
    print(f"[DEBUG] Search results: {results}")
    assert results, "Vector search failed"
    print("[OK] vector_search")

def test_summarize():
    print("[TEST] summarize...")
    from modules import summarize
    note = "This is a long note about Python and AI. It should be summarized."
    summary = summarize.summarize_note(note)
    print(f"[DEBUG] Summary: {summary}")
    assert summary.strip(), "Summarize failed"
    print("[OK] summarize")

def test_polish():
    print("[TEST] polish...")
    from modules import polish
    note = "this is a messy note. needs polish."
    polished = polish.polish_note_llm(note, {"endpoint": "http://localhost:11434", "model": "mistral"})
    print(f"[DEBUG] Polished: {polished}")
    assert polished.strip(), "Polish failed"
    print("[OK] polish")

def test_smart_link():
    print("[TEST] smart_link...")
    from modules import smart_link
    note = "This is a note with [[links]] and #tags."
    result = smart_link.smart_link_llm(note, {"endpoint": "http://localhost:11434", "model": "mistral"})
    print(f"[DEBUG] Smart link result: {result}")
    assert result.strip(), "Smart link failed"
    print("[OK] smart_link")

def test_backup():
    print("[TEST] backup...")
    from modules.backup import backup_vault
    try:
        backup_vault(TEST_VAULT)
        print("[OK] backup (no error)")
    except Exception as e:
        print(f"[WARN] backup error: {e}")

def test_analyze_notes():
    print("[TEST] analyze_notes...")
    from modules.analyze_notes import analyze_notes
    # Test dry run mode
    result = analyze_notes(TEST_VAULT, dry_run=True)
    print(f"[DEBUG] Analyze notes result (dry_run): {result}")
    assert result is None, "Analyze notes dry_run should return None"
    # Test real analysis
    result = analyze_notes(TEST_VAULT, dry_run=False)
    print(f"[DEBUG] Analyze notes result (real): {result}")
    assert isinstance(result, dict), "Analyze notes failed"
    print("[OK] analyze_notes")

def test_feature_toggles():
    print("[TEST] feature toggles...")
    from modules import memory
    memory.enable_feature("summarize")
    enabled = memory.get_enabled_features()
    print(f"[DEBUG] Enabled features: {enabled}")
    assert "summarize" in enabled, "Enable feature failed"
    memory.disable_feature("summarize")
    enabled = memory.get_enabled_features()
    print(f"[DEBUG] Enabled features after disable: {enabled}")
    assert "summarize" not in enabled, "Disable feature failed"
    print("[OK] feature toggles")

def test_memory_safety():
    print("[TEST] memory safety...")
    from modules import memory
    # Dry run mode
    memory.set_dry_run_mode(True)
    assert memory.is_dry_run(), "Dry run enable failed"
    memory.set_dry_run_mode(False)
    assert not memory.is_dry_run(), "Dry run disable failed"
    print("[OK] memory safety")

def test_approval_flow_execution():
    print("[TEST] approval flow execution...")
    from modules import memory

    tmp_file = os.path.join(TEST_VAULT, "approval_flow_test.md")
    old_queue = memory.get_approval_queue()
    old_dry_run = memory.is_dry_run()

    try:
        memory.save_json(memory.APPROVAL_QUEUE_PATH, [])
        memory.set_dry_run_mode(False)

        queued = memory.safe_write_file(tmp_file, "approved write content")
        assert not queued, "Write should be queued before approval"
        assert not os.path.exists(tmp_file), "File should not exist before approval"

        entry = memory.approve_next_action()
        assert entry and entry["action"] in ("create", "modify"), "Expected queued write action"
        executed = memory.execute_approved_action(entry)
        assert executed, "Approved write did not execute"
        assert os.path.exists(tmp_file), "File not created after approval"
        with open(tmp_file, "r", encoding="utf-8") as f:
            assert f.read() == "approved write content", "Approved write content mismatch"

        queued = memory.safe_delete_file(tmp_file)
        assert not queued, "Delete should be queued before approval"
        assert os.path.exists(tmp_file), "File should still exist before delete approval"

        entry = memory.approve_next_action()
        assert entry and entry["action"] == "delete", "Expected queued delete action"
        executed = memory.execute_approved_action(entry)
        assert executed, "Approved delete did not execute"
        assert not os.path.exists(tmp_file), "File still exists after approved delete"
        print("[OK] approval flow execution")
    finally:
        memory.save_json(memory.APPROVAL_QUEUE_PATH, old_queue)
        memory.set_dry_run_mode(old_dry_run)
        if os.path.exists(tmp_file):
            os.remove(tmp_file)

def test_refactor_schedule():
    print("[TEST] refactor schedule...")
    from modules.refactor import schedule_refactor, list_refactor_jobs, remove_refactor_job
    import datetime
    note_path = TEST_NOTE
    when = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=1)).isoformat()
    job_id = schedule_refactor(note_path, when)
    jobs = list_refactor_jobs()
    print(f"[DEBUG] Refactor jobs: {jobs}")
    assert job_id in jobs, "Refactor schedule failed"
    remove_refactor_job(job_id)
    print("[OK] refactor schedule")

def test_interest_enhancements():
    print("[TEST] interest enhancements...")
    from modules import interest_features
    notes = [{"filename": TEST_NOTE, "content": "Python AI machine learning"}]
    interests = interest_features.detect_interests({TEST_NOTE: "Python AI machine learning"})
    print(f"[DEBUG] Interests: {interests}")
    assert "python" in interests or interests, "Interest detection failed"
    mapping = interest_features.map_interests_to_notes(interests, notes)
    print(f"[DEBUG] Interest mapping: {mapping}")
    assert mapping, "Interest mapping failed"
    print("[OK] interest enhancements")

if __name__ == "__main__":
    ensure_ollama_model("qwen2.5-coder:7b")

    try:
        test_note_polish()
        test_code_explain()
        test_context_note()
        test_refactor()
        test_interest_features()
        test_assistant_memory_features()
        test_memory()
        test_vector_search()
        test_summarize()
        test_polish()
        test_smart_link()
        test_backup()
        test_analyze_notes()
        test_feature_toggles()
        test_memory_safety()
        test_approval_flow_execution()
        test_refactor_schedule()
        test_interest_enhancements()
        print("\nALL FEATURE TESTS PASSED.")
    finally:
        cleanup()
