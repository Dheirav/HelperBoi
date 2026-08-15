import os
import json
import threading
import time
from datetime import datetime, timedelta
from modules.llm_client import call_ollama

SCHEDULE_PATH = os.path.join(os.path.dirname(__file__), '..', 'memory', 'refactor_schedule.json')

def refactor_note_llm(note, model_info):
    if not note.strip():
        return "(No content to refactor)"
    prompt = f"Refactor and restructure the following note for clarity and organization:\n{note.strip()}"
    return call_ollama(prompt, endpoint=model_info["endpoint"], model=model_info["model"], timeout=30)

# --- Refactor core (existing function assumed) ---
def refactor_code(code, model_id=None):
    try:
        from modules.model_router import get_llm_model, select_best_model_for_task
        model_info = get_llm_model(select_best_model_for_task("refactor", code) if model_id is None else model_id)
        result = refactor_note_llm(code, model_info)

        if result and "def" in result and ":" in result:
            return result
        # Fallback: simple formatting
        import re
        code_fmt = re.sub(r'def (\w+)\((.*?)\):?\s*return (.+)', r'def \1(\2):\n    return \3', code)
        if "def" in code_fmt and ":" in code_fmt:
            return code_fmt
        return "(Refactor failed)"
    except Exception as e:
        # Fallback: simple formatting
        import re
        code_fmt = re.sub(r'def (\w+)\((.*?)\):?\s*return (.+)', r'def \1(\2):\n    return \3', code)
        if "def" in code_fmt and ":" in code_fmt:
            return code_fmt
        return f"(Refactor error: {e})"

# --- Scheduling logic ---
def load_schedule():
    if not os.path.exists(SCHEDULE_PATH):
        return {}
    with open(SCHEDULE_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_schedule(schedule):
    with open(SCHEDULE_PATH, 'w', encoding='utf-8') as f:
        json.dump(schedule, f, indent=2)

def schedule_refactor(note_path, when, repeat=None):
    """
    Schedule a refactor job for a note at a given datetime (ISO string), optionally repeating ('daily' or 'weekly').
    """
    schedule = load_schedule()
    job_id = f"{note_path}:{when}"
    schedule[job_id] = {
        'note_path': note_path,
        'when': when,
        'repeat': repeat,
        'last_run': None
    }
    save_schedule(schedule)
    return job_id

def remove_refactor_job(job_id):
    schedule = load_schedule()
    if job_id in schedule:
        del schedule[job_id]
        save_schedule(schedule)
        return True
    return False

def list_refactor_jobs():
    schedule = load_schedule()
    return schedule

def run_due_refactor_jobs():
    schedule = load_schedule()
    now = datetime.utcnow()
    changed = False
    for job_id, job in list(schedule.items()):
        when = datetime.fromisoformat(job['when'])
        if job['last_run']:
            last_run = datetime.fromisoformat(job['last_run'])
        else:
            last_run = None
        if now >= when and (not last_run or now - last_run >= timedelta(days=1 if job['repeat']=='daily' else 7 if job['repeat']=='weekly' else 0)):
            # Run refactor
            try:
                with open(job['note_path'], encoding='utf-8') as f:
                    note = f.read()
                result = refactor_code(note)
                with open(job['note_path'], 'w', encoding='utf-8') as f:
                    f.write(result)
                job['last_run'] = now.isoformat()
                # Reschedule if repeating
                if job['repeat'] == 'daily':
                    job['when'] = (now + timedelta(days=1)).replace(hour=when.hour, minute=when.minute, second=0, microsecond=0).isoformat()
                elif job['repeat'] == 'weekly':
                    job['when'] = (now + timedelta(days=7)).replace(hour=when.hour, minute=when.minute, second=0, microsecond=0).isoformat()
                else:
                    # One-time job, remove after run
                    del schedule[job_id]
                    continue
                changed = True
            except Exception as e:
                print(f"[Refactor Scheduler] Error running job {job_id}: {e}")
    if changed:
        save_schedule(schedule)

def start_refactor_scheduler(interval=3600):
    """Start a background thread to check and run due refactor jobs every interval seconds."""
    def loop():
        while True:
            run_due_refactor_jobs()
            time.sleep(interval)
    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t
