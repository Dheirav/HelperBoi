"""
Unified RAG Context Auto-Injection Module for HelperBoi / Jarvis
Automatically retrieves relevant Obsidian notes and assistant memory to inject context into LLM prompts.
"""

import logging
import os
from modules import vector_search, assistant_memory_features
from modules.llm_client import call_ollama
from modules.model_router import get_llm_model, select_best_model_for_task

logger = logging.getLogger("jarvis.rag_context")


def build_rag_context(user_prompt, vault_path=None, top_k=3):
    """
    Query vector search and assistant memory to build a retrieved knowledge context block.
    """
    context_blocks = []

    # 1. Retrieve top matching Obsidian notes via vector search
    try:
        if vault_path and os.path.exists(vault_path):
            results = vector_search.search(user_prompt, top_k=top_k, vault_path=vault_path, verbose=False)
            if results:
                note_snippets = []
                for filepath, score in results:
                    basename = os.path.basename(filepath)
                    try:
                        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                            snippet = f.read(500).replace("\n", " ")
                        note_snippets.append(f"• Note [{basename}] (relevance {score:.2f}): \"{snippet}\"")
                    except Exception:
                        pass
                if note_snippets:
                    context_blocks.append("--- Relevant Vault Notes ---\n" + "\n".join(note_snippets))
    except Exception as e:
        logger.warning(f"Vector search failed during RAG context build: {e}")

    # 2. Retrieve recent assistant task history
    try:
        task_log = assistant_memory_features.get_task_log()
        if task_log:
            recent_tasks = task_log[-3:]
            task_snippets = [f"• Task [{t.get('task')}] at {t.get('timestamp')}" for t in recent_tasks]
            context_blocks.append("--- Recent Activity Log ---\n" + "\n".join(task_snippets))
    except Exception as e:
        logger.warning(f"Task log retrieval failed during RAG context build: {e}")

    if not context_blocks:
        return ""

    return "\n\n[RETRIEVED KNOWLEDGE CONTEXT]\n" + "\n\n".join(context_blocks) + "\n[END CONTEXT]\n\n"


def inject_rag_and_call(user_prompt, system_instruction=None, model_id=None, vault_path=None):
    """
    Retrieve RAG context, prepend to prompt, and query the LLM.
    """
    rag_prefix = build_rag_context(user_prompt, vault_path=vault_path)
    
    full_prompt = (system_instruction or "You are Jarvis, an intelligent personal AI assistant.\nAnswer the user query accurately using the provided knowledge context when relevant.\n")
    full_prompt += f"\n{rag_prefix}User Query: \"{user_prompt}\"\n\nJarvis Response:"

    model_info = get_llm_model(model_id or select_best_model_for_task("context_note", user_prompt))
    return call_ollama(full_prompt, endpoint=model_info["endpoint"], model=model_info["model"], timeout=30)
