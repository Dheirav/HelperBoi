from modules.llm_client import call_ollama
from modules.model_router import get_llm_model, select_best_model_for_task

def polish_note_llm(note, model_info):
    if not note.strip():
        return "(No content to polish)"
    prompt = f"Polish and clean up the following note, fixing grammar, formatting, and making it clear and concise.\n{note.strip()}"
    return call_ollama(prompt, endpoint=model_info["endpoint"], model=model_info["model"], timeout=30)

def polish_note(note, model_id=None):
    """Clean up and polish a note using the selected or default LLM model."""
    if model_id is None:
        model_id = select_best_model_for_task("polish", note)
    model_info = get_llm_model(model_id)
    return polish_note_llm(note, model_info)

