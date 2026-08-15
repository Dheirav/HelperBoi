import os
from modules.llm_client import call_ollama

def smart_link_llm(note, model_info, vault_path=None, split=False):
    if not note.strip():
        return "(No content to link)"
    context = ""
    if vault_path:
        # Load recent notes for context-aware linking
        notes = []
        for root, dirs, files in os.walk(vault_path):
            for file in files:
                if file.endswith('.md'):
                    with open(os.path.join(root, file), encoding='utf-8', errors='ignore') as f:
                        notes.append(f.read())
        context = "\n---\n".join(notes[-5:]) if notes else ""
    split_hint = "Split the note into atomic notes if it contains multiple ideas. " if split else ""
    prompt = (
        f"{split_hint}Suggest smart links and backlinks for the following note. "
        f"If possible, add [[wikilinks]] to related concepts or notes. "
        f"If context is provided, use it to suggest backlinks to existing notes.\n"
        f"Context notes:\n{context}\n---\nNote:\n{note.strip()}"
    )
    return call_ollama(prompt, endpoint=model_info["endpoint"], model=model_info["model"], timeout=30)
