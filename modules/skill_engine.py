"""
Skill Engine for HelperBoi / Jarvis
Manages dynamic creation, testing, registration, and execution of custom skills in skills/
"""

import os
import sys
import json
import logging
import importlib.util
import py_compile
import shutil
from modules.memory import request_file_action, safe_write_file
from modules.llm_client import call_ollama
from modules.model_router import get_llm_model, select_best_model_for_task

logger = logging.getLogger("jarvis.skill_engine")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKILLS_DIR = os.path.join(PROJECT_ROOT, "skills")
DRAFTS_DIR = os.path.join(PROJECT_ROOT, "scratch", "skill_drafts")

os.makedirs(SKILLS_DIR, exist_ok=True)
os.makedirs(DRAFTS_DIR, exist_ok=True)


def sanitize_skill_name(name):
    """Sanitize skill name to alphanumeric + underscores."""
    clean = "".join(c if c.isalnum() or c == "_" else "_" for c in name.lower())
    return clean.strip("_") or "unnamed_skill"


def list_skills():
    """Return dictionary of registered skills and their descriptions."""
    skills = {}
    if not os.path.exists(SKILLS_DIR):
        return skills

    for item in os.listdir(SKILLS_DIR):
        skill_path = os.path.join(SKILLS_DIR, item)
        if os.path.isdir(skill_path):
            doc_file = os.path.join(skill_path, "SKILL.md")
            desc = "Custom skill"
            if os.path.exists(doc_file):
                try:
                    with open(doc_file, "r", encoding="utf-8", errors="ignore") as f:
                        desc = f.read()[:200].replace("\n", " ")
                except Exception:
                    pass
            skills[item] = desc
    return skills


def create_skill_draft(skill_name, description, python_code):
    """
    Draft a new skill into scratch/skill_drafts/<skill_name>/ and request approval.
    """
    clean_name = sanitize_skill_name(skill_name)
    draft_dir = os.path.join(DRAFTS_DIR, clean_name)
    os.makedirs(draft_dir, exist_ok=True)

    skill_md_path = os.path.join(draft_dir, "SKILL.md")
    tool_py_path = os.path.join(draft_dir, "tool.py")

    skill_md_content = f"# Skill: {clean_name}\n\n{description}\n"
    
    with open(skill_md_path, "w", encoding="utf-8") as f:
        f.write(skill_md_content)
    with open(tool_py_path, "w", encoding="utf-8") as f:
        f.write(python_code)

    # Validate syntax via py_compile
    try:
        py_compile.compile(tool_py_path, doraise=True)
    except py_compile.PyCompileError as e:
        logger.error(f"Skill Python code syntax error: {e}")
        return False, f"Syntax Error: {e}"

    target_skill_dir = os.path.join(SKILLS_DIR, clean_name)
    request_file_action("create_skill", target_skill_dir, new_content=json.dumps({
        "skill_name": clean_name,
        "description": description,
        "draft_dir": draft_dir,
        "target_dir": target_skill_dir
    }))

    return True, f"Skill '{clean_name}' drafted and submitted for approval. Use 'jarvis approve' to activate."


def register_approved_skill(payload):
    """Register an approved skill payload into skills/."""
    try:
        data = json.loads(payload) if isinstance(payload, str) else payload
        clean_name = data["skill_name"]
        draft_dir = data["draft_dir"]
        target_dir = data["target_dir"]

        os.makedirs(target_dir, exist_ok=True)
        shutil.copytree(draft_dir, target_dir, dirs_exist_ok=True)

        logger.info(f"Registered approved skill: {clean_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to register approved skill: {e}")
        return False



def execute_skill(skill_name, **kwargs):
    """
    Dynamically import and execute a registered skill tool.
    """
    clean_name = sanitize_skill_name(skill_name)
    skill_py = os.path.join(SKILLS_DIR, clean_name, "tool.py")

    if not os.path.exists(skill_py):
        return f"[ERROR] Skill '{clean_name}' not found in registered skills."

    try:
        spec = importlib.util.spec_from_file_location(f"skills.{clean_name}", skill_py)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if hasattr(module, "run"):
            return module.run(**kwargs)
        elif hasattr(module, "main"):
            return module.main(**kwargs)
        else:
            return f"[ERROR] Skill 'tool.py' does not define a 'run(**kwargs)' or 'main(**kwargs)' entry point."
    except Exception as e:
        logger.error(f"Skill execution failed for '{clean_name}': {e}")
        return f"[ERROR] Skill execution failed: {e}"


def generate_skill_from_prompt(prompt_text, model_id=None):
    """
    Use LLM (qwen2.5-coder:7b) to generate a Python tool script and SKILL.md description from user prompt.
    """
    model_info = get_llm_model(model_id or select_best_model_for_task("refactor", prompt_text))

    sys_prompt = (
        "You are an expert Python tool developer for Jarvis AI Assistant.\n"
        "Generate a complete Python script for a custom tool based on the user's request.\n\n"
        "CRITICAL REQUIREMENTS:\n"
        "1. The Python code MUST define a function `def run(**kwargs):` that accepts arguments and returns a string result.\n"
        "2. Include all necessary standard library imports.\n"
        "3. Output ONLY a valid JSON object matching this structure (no extra text, no markdown fences):\n"
        "{\n"
        '  "skill_name": "<short_snake_case_name>",\n'
        '  "description": "<detailed description of what tool does>",\n'
        '  "python_code": "<complete python file content>"\n'
        "}\n\n"
        f"User Prompt: \"{prompt_text}\"\n"
        "JSON Output:"
    )

    try:
        raw_resp = call_ollama(sys_prompt, endpoint=model_info["endpoint"], model=model_info["model"], timeout=30)
        if raw_resp.startswith("(LLM error"):
            return False, f"LLM Generation Failed: {raw_resp}"

        cleaned = raw_resp.strip()
        cleaned = cleaned.replace("```json", "").replace("```", "").strip()
        data = json.loads(cleaned)

        name = data.get("skill_name", "custom_tool")
        desc = data.get("description", prompt_text)
        code = data.get("python_code", "")

        if not code or "def run(" not in code:
            return False, "Generated code missing `def run(**kwargs):` entry point."

        return create_skill_draft(name, desc, code)
    except Exception as e:
        logger.error(f"Failed to generate skill from LLM: {e}")
        return False, f"Failed to generate skill: {e}"
