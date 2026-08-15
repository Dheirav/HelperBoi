from modules.llm_client import call_ollama

def summarize_note_llm(note, model_info, level="short"):
    if not note.strip():
        return "(No content to summarize)"
    if level == "short":
        prompt = f"Summarize the following note in 1-2 sentences:\n{note.strip()}"
    elif level == "medium":
        prompt = f"Summarize the following note in a short paragraph:\n{note.strip()}"
    elif level == "detailed":
        prompt = f"Summarize the following note in detail, covering all key points:\n{note.strip()}"
    else:
        prompt = f"Summarize the following note:\n{note.strip()}"
    return call_ollama(prompt, endpoint=model_info["endpoint"], model=model_info["model"], debug=True)

# Provide a consistent summarize_note interface for import
def summarize_note(note, level="medium", model_id=None):
    from modules.model_router import get_llm_model
    model_info = get_llm_model(model_id)
    return summarize_note_llm(note, model_info, level=level)

