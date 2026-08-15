import os
import sys
import importlib
from modules.llm_client import call_ollama

def get_all_notes_from_vault(vault_path):
    notes = []
    for root, dirs, files in os.walk(vault_path):
        for file in files:
            if file.endswith('.md'):
                with open(os.path.join(root, file), encoding='utf-8', errors='ignore') as f:
                    notes.append(f.read())
    return notes

def context_aware_note_generation(prompt, model_info, vault_path, note_type=None):
    notes = get_all_notes_from_vault(vault_path)
    context = "\n---\n".join(notes[-5:]) if notes else ""
    type_hint = f"Type: {note_type}. " if note_type else ""
    full_prompt = (
        f"{type_hint}Using the following recent notes as context, generate a new note based on the prompt below. "
        f"Be aware that the system contains different types of notes (e.g., zettelkasten, meeting, task, journal, etc).\n"
        f"Context notes:\n{context}\n---\nPrompt: {prompt}"
    )
    return call_ollama(full_prompt, endpoint=model_info["endpoint"], model=model_info["model"], timeout=60)

def get_llm_model(model_id=None):
    from modules.model_router import get_llm_model as router_get_llm_model
    return router_get_llm_model(model_id)


def generate_context_note(prompt, vault_path, model_id=None, note_type=None):
    """Generate a context-aware note using the default or selected LLM model."""
    model_info = get_llm_model(model_id)
    return context_aware_note_generation(prompt, model_info, vault_path, note_type=note_type)
