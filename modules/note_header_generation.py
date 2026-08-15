"""
Module: note_header_generation.py
Feature: Generate comprehensive, logically grouped atomic note headers from topics/subtopics/rough notes
"""

from typing import List, Optional
import importlib
from modules.llm_client import call_ollama

def extract_headers_llm(topics, subtopics, rough_notes, model_id=None):
    """
    Use the LLM to extract atomic note headers from topics, subtopics, and rough notes.
    """
    # Dynamically import get_llm_model from main.py
    main_mod = importlib.import_module('main')
    get_llm_model = main_mod.get_llm_model
    from modules.model_router import select_best_model_for_task
    prompt = (
        "Extract a comprehensive, logically grouped list of atomic note headers for Zettelkasten-style notes.\n"
        f"Topics: {topics if topics else []}\n"
        f"Subtopics: {subtopics if subtopics else []}\n"
        f"Rough Notes: {rough_notes if rough_notes else ''}\n\n"
        "Return only a Python list of strings, each string being a note header. Do not include explanations or extra text."
    )
    # Model selection
    model_info = get_llm_model(select_best_model_for_task("note_header_generation", prompt) if model_id is None else model_id)
    response = call_ollama(prompt, endpoint=model_info["endpoint"], model=model_info["model"], timeout=60)
    import ast
    try:
        headers = ast.literal_eval(response)
        if not isinstance(headers, list):
            raise ValueError("LLM did not return a list.")
        # Remove duplicates, preserve order
        seen = set()
        unique_headers = []
        for h in headers:
            if h not in seen:
                unique_headers.append(h)
                seen.add(h)
        return unique_headers
    except Exception as e:
        print(f"LLM header extraction failed: {e}\nFalling back to rules-based extraction.\nRaw LLM output: {response}")
        return None

class NoteHeaderGenerator:
    """
    Generates Zettelkasten-style atomic note headers from topics, subtopics, and/or rough notes.
    """
    def __init__(self):
        pass

    def generate_headers(self, topics: List[str], subtopics: Optional[List[str]] = None, rough_notes: Optional[str] = None, model_id=None) -> List[str]:
        """
        Generate a comprehensive, logically grouped list of atomic note headers using LLM extraction if available.
        Args:
            topics: List of topics (section headers)
            subtopics: Optional list of subtopics (subsection headers)
            rough_notes: Optional string of rough notes
            model_id: Optional model id for LLM
        Returns:
            List of atomic note headers (strings)
        """
        # Compose a prompt that matches the style of the provided example
        prompt = (
            "Given the following topics and subtopics for a NumPy guide, extract a comprehensive, logically grouped list of atomic note headers suitable for Zettelkasten-style notes. "
            "Each header should be self-contained and cover a single concept or operation. "
            "Return only a Python list of strings, each string being a note header. Do not include explanations or extra text.\n\n"
            f"Topics: {topics if topics else []}\n"
            f"Subtopics: {subtopics if subtopics else []}\n"
            f"Rough Notes: {rough_notes if rough_notes else ''}"
        )
        # Model selection and LLM call (follows project pattern)
        try:
            import importlib
            main_mod = importlib.import_module('main')
            get_llm_model = main_mod.get_llm_model
            from modules.model_router import select_best_model_for_task
            # Use call_ollama from modules.context_note (shared LLM util)
            from modules.context_note import call_ollama
            model_info = get_llm_model(select_best_model_for_task("note_header_generation", prompt) if model_id is None else model_id)
            response = call_ollama(prompt, endpoint=model_info["endpoint"], model=model_info["model"], timeout=60)
            import ast
            headers = ast.literal_eval(response)
            if not isinstance(headers, list):
                raise ValueError("LLM did not return a list.")
            # Remove duplicates, preserve order
            seen = set()
            unique_headers = []
            for h in headers:
                if h not in seen:
                    unique_headers.append(h)
                    seen.add(h)
            return unique_headers
        except Exception as e:
            print(f"LLM header extraction failed: {e}\nFalling back to rules-based extraction.")
            # Fallback to rules-based extraction
            headers = []
            # Add topics as headers
            if topics:
                headers.extend([t.strip() for t in topics if t.strip()])
            # Add subtopics as headers (grouped under topics if possible)
            if subtopics:
                headers.extend([s.strip() for s in subtopics if s.strip() and s.strip() not in headers])
            # Extract possible headers from rough notes (simple split by lines, filter short lines)
            if rough_notes:
                for line in rough_notes.splitlines():
                    line = line.strip()
                    if len(line) > 3 and line not in headers:
                        headers.append(line)
            # Remove duplicates, preserve order
            seen = set()
            unique_headers = []
            for h in headers:
                if h not in seen:
                    unique_headers.append(h)
                    seen.add(h)
            return unique_headers

    def review_headers(self, headers: List[str]) -> List[str]:
        """
        Allow user to review/edit headers before note generation (CLI interactive).
        Args:
            headers: List of generated headers
        Returns:
            List of reviewed/edited headers
        """
        print("\nGenerated Note Headers:")
        for i, h in enumerate(headers):
            print(f"  [{i+1}] {h}")
        print("\nYou may edit the headers. Press Enter to keep, or type a new value. Type a single dash '-' to delete.")
        reviewed = []
        for i, h in enumerate(headers):
            new_h = input(f"Header {i+1} [{h}]: ")
            if new_h.strip() == '-':
                continue  # skip/delete
            if new_h.strip() == '':
                reviewed.append(h)  # keep original if blank
            else:
                reviewed.append(new_h.strip())
        print(f"\nFinal headers ({len(reviewed)}): {reviewed}")
        return reviewed
