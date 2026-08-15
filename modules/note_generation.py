"""
Module: note_generation.py
Feature: Zettelkasten-style atomic note generation for topics/notes
"""

import os
from typing import List, Dict, Optional
from modules.note_header_generation import NoteHeaderGenerator

class NoteGenerator:
    """
    Generates Zettelkasten-style atomic notes from topics, subtopics, and/or rough notes.
    Workflow:
        1. Generate comprehensive, logically grouped atomic note headers (delegated)
        2. Allow user review/edit of headers (optional, delegated)
        3. Generate full notes for each header (using preferred structure)
        4. Export notes as Obsidian-compatible Markdown files
    """

    def __init__(self, output_dir: str = "test_vault"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.header_generator = NoteHeaderGenerator()

    def run_workflow(self, topics: List[str], subtopics: Optional[List[str]] = None, rough_notes: Optional[str] = None, context: Optional[str] = None):
        """
        Complete workflow: generate headers, review, generate notes, and export.
        Args:
            topics: List of topics
            subtopics: Optional list of subtopics
            rough_notes: Optional string of rough notes
            context: Optional context/notes to inform note content
        Returns:
            List of exported note file paths

        Reshaping Arrays with `reshape()` and `reshape(-1)`
        Flattening Arrays: `ravel`, `flatten`
        Transposing and Swapping Axes: `.T`, `transpose()`, `swapaxes()`, `moveaxis()`
        Expanding or Removing Dimensions: `newaxis`, `expand_dims`, `squeeze()`
        Rolling and Shifting Axes: `rollaxis` (legacy)
        Understanding Views vs Copies in NumPy
    
        """
        print(f"[DEBUG] Topics: {topics}")
        print(f"[DEBUG] Subtopics: {subtopics}")
        print(f"[DEBUG] Rough notes: {rough_notes}")
        # 1. Generate headers
        headers = self.header_generator.generate_headers(topics, subtopics=subtopics, rough_notes=rough_notes)
        print(f"[DEBUG] Headers generated: {headers}")
        if not headers:
            print("[ERROR] No headers generated. Aborting note generation.")
            return []
        # 2. Review headers (optional)
        reviewed_headers = self.header_generator.review_headers(headers)
        print(f"[DEBUG] Headers after review: {reviewed_headers}")
        if not reviewed_headers:
            print("[ERROR] No headers after review. Aborting note generation.")
            return []
        # 3. Generate notes with progress indicator
        print("\n[⏳] Generating notes:")
        notes = {}
        total = len(reviewed_headers)
        for idx, header in enumerate(reviewed_headers, 1):
            print(f"  [{idx}/{total}] {header} ...", end='', flush=True)
            note = self.generate_notes([header], context=context)[header]
            print(" done.")
            notes[header] = note
        print(f"[DEBUG] Notes generated: {list(notes.keys())}")
        if not notes:
            print("[ERROR] No notes generated. Aborting export.")
            return []
        # 4. Export notes (sanitize filenames)
        self.export_notes(notes)
        print(f"[DEBUG] Notes exported to: {self.output_dir}")
        return [os.path.join(self.output_dir, f"{self.sanitize_filename(header)}.md") for header in reviewed_headers]

    @staticmethod
    def sanitize_filename(header: str) -> str:
        """Sanitize header to be a safe filename (alphanumeric, underscores, dashes). Remove forbidden characters for Windows."""
        import re
        # Remove forbidden Windows filename characters: * " / \ < > : | ?
        forbidden = r'[\\/*?\:"<>|]'
        name = re.sub(forbidden, '', header)
        name = re.sub(r'[^\w\- ]', '', name)  # keep alphanumeric, dash, underscore, space
        name = name.replace(' ', '_')
        return name[:100]  # limit length for safety

    def generate_notes(self, headers: List[str], context: Optional[str] = None) -> Dict[str, str]:
        """
        Generate full notes for each header using LLM-powered content generation, following the user's Zettelkasten structure and conventions.
        Args:
            headers: List of note headers
            context: Optional context/notes to inform note content
        Returns:
            Dict mapping header to note content (Markdown)
        """
        import importlib
        from modules.model_router import select_best_model_for_task
        from modules.llm_client import call_ollama
        main_mod = importlib.import_module('main')
        get_llm_model = main_mod.get_llm_model
        notes = {}
        for header in headers:
            prompt = (
                f"Write a complete, standalone Zettelkasten-style atomic note for the following topic. "
                f"Follow this structure, but adapt as needed for completeness and clarity.\n"
                f"Header: {header}\n"
                f"Context: {context if context else ''}\n"
                "\nStructure (use as a guide, not a strict template):\n"
                "1. Definition (relevance in programming/data science)\n"
                "2. Intuitive Explanation (analogies, simple language)\n"
                "3. Properties & Rules (constraints, relationships)\n"
                "4. Syntax & Usage (with ~~~ code blocks)\n"
                "5. Examples (including edge cases, ~~~ code blocks)\n"
                "6. Performance Considerations\n"
                "7. Common Mistakes & Best Practices\n"
                "8. Use Cases & Applications\n"
                "9. Comparison with Related Concepts\n"
                "10. Linking Notes (related topics, logical progression)\n"
                "\n- All code blocks must use ~~~.\n- Do not repeat the header as a title inside the note.\n- The note must be exhaustive, clear, and functionally complete.\n- Avoid redundancy, but ensure completeness.\n- Link to related notes where overlap happens.\n"
            )
            model_info = get_llm_model(select_best_model_for_task("note_content_generation", prompt))
            note_content = call_ollama(prompt, endpoint=model_info["endpoint"], model=model_info["model"])
            # Add header as markdown title for Obsidian compatibility
            notes[header] = f"# {header}\n\n{note_content.strip()}\n"
        return notes

    def export_notes(self, notes: Dict[str, str]):
        """
        Export notes as Obsidian-compatible Markdown files in output_dir.
        Args:
            notes: Dict mapping header to note content
        """
        for header, content in notes.items():
            filename = f"{self.sanitize_filename(header)}.md"
            path = os.path.join(self.output_dir, filename)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)

    def estimate_coverage(self, headers: List[str], topics: List[str], subtopics: Optional[List[str]] = None) -> float:
        """
        Estimate coverage of headers over the provided topics/subtopics (simple heuristic).
        Args:
            headers: List of generated headers
            topics: List of topics
            subtopics: Optional list of subtopics
        Returns:
            Estimated coverage as a float between 0 and 1
        """
        # Simple heuristic: ratio of unique topic/subtopic words covered by headers
        all_keywords = set([t.lower() for t in topics])
        if subtopics:
            all_keywords.update([s.lower() for s in subtopics])
        header_words = set()
        for h in headers:
            header_words.update(h.lower().split())
        if not all_keywords:
            return 1.0 if headers else 0.0
        covered = sum(1 for k in all_keywords if k in header_words)
        return covered / len(all_keywords)

# TODO: Add CLI integration (main.py or modular_cli.py) to trigger note generation workflow
