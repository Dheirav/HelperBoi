"""
Skill Builder Module for HelperBoi / Jarvis
Allows Jarvis to dynamically write, validate, register, and execute custom Python skills
when encountering missing tools or capability gaps.
"""

import os
import re
import logging
import ast
from modules.llm_client import call_ollama
from modules.model_router import get_llm_model
from modules.skill_engine import register_approved_skill, execute_skill, sanitize_skill_name

logger = logging.getLogger("jarvis.skill_builder")


def generate_skill_code(skill_name, requirement_description, model_id=None):
    """
    Use LLM to generate standalone Python skill code for run(input_text).
    Returns string containing python code.
    """
    model = model_id or get_llm_model("code")
    clean_name = sanitize_skill_name(skill_name)

    prompt = (
        f"You are the Custom Skill Code Generator for Jarvis AI Assistant.\n"
        f"Write a clean, safe, standalone Python script for a skill named '{clean_name}'.\n"
        f"Requirement: {requirement_description}\n\n"
        "STRICT REQUIREMENTS:\n"
        "1. Define a main function `def run(input_text):\n` as the entry point.\n"
        "2. The function MUST return a human-readable string summary or result.\n"
        "3. Only use standard library modules (os, sys, subprocess, urllib, json, re, math, etc.).\n"
        "4. Output ONLY valid executable Python code wrapped in ```python ... ``` fences. No extra chat.\n\n"
        "Python Code:"
    )

    try:
        raw_output = call_ollama(prompt, model=model)
        # Extract code block
        match = re.search(r"```python(.*?)```", raw_output, re.DOTALL)
        if match:
            code = match.group(1).strip()
        else:
            code = raw_output.replace("```", "").strip()
        return code
    except Exception as e:
        logger.error(f"Failed to generate skill code for '{clean_name}': {e}")
        return None


def validate_skill_code(code_str):
    """
    Validate Python syntax and verify presence of entry point run(input_text).
    Returns (bool, str) tuple.
    """
    if not code_str or not isinstance(code_str, str):
        return False, "Code string is empty."

    try:
        compile(code_str, "<generated_skill>", "exec")
    except SyntaxError as se:
        return False, f"Syntax Error on line {se.lineno}: {se.msg}"
    except Exception as e:
        return False, f"Compilation error: {e}"

    # Verify AST contains def run(...)
    try:
        parsed = ast.parse(code_str)
        func_names = [node.name for node in ast.walk(parsed) if isinstance(node, ast.FunctionDef)]
        if "run" not in func_names:
            return False, "Skill code is missing required entry point function `run(input_text)`."
    except Exception as e:
        return False, f"AST parsing failed: {e}"

    return True, "Valid"


def create_and_register_skill(skill_name, code_str, description="Auto-generated custom skill"):
    """
    Write generated skill code to a temporary draft directory and register it into skills/.
    Returns (bool, str) tuple.
    """
    clean_name = sanitize_skill_name(skill_name)
    valid, err = validate_skill_code(code_str)
    if not valid:
        return False, f"Validation failed: {err}"

    draft_dir = os.path.join(os.path.dirname(__file__), "..", "scratch", f"draft_{clean_name}")
    os.makedirs(draft_dir, exist_ok=True)

    tool_path = os.path.join(draft_dir, "tool.py")
    doc_path = os.path.join(draft_dir, "SKILL.md")

    with open(tool_path, "w", encoding="utf-8") as f:
        f.write(code_str)

    with open(doc_path, "w", encoding="utf-8") as f:
        f.write(f"# Skill: {clean_name}\n\n{description}\n")

    payload = {
        "skill_name": clean_name,
        "description": description,
        "draft_dir": draft_dir
    }

    ok = register_approved_skill(payload)
    if ok:
        return True, f"Skill '{clean_name}' successfully registered under skills/{clean_name}/!"
    return False, "Failed to register skill with skill_engine."


def is_text_content_generation_request(user_input):
    """
    Safeguard check: returns True if prompt is asking for text/content generation
    (essay, poem, article, summary, explanation, letter, email) which should be handled
    by LLM prompt/RAG context instead of creating a Python code skill.
    """
    text = str(user_input).lower()
    text_keywords = [
        "essay", "article", "story", "poem", "letter", "email", "summary", "paragraph",
        "explanation", "post", "blog", "draft", "write a", "write an", "generate a 1000",
        "create a 1000", "word essay", "word story"
    ]
    return any(kw in text for kw in text_keywords)


def find_existing_matching_skill(action_name, user_input):
    """
    Check if an existing built-in tool or custom skill in skills/ already handles this task
    or can handle it with parameter adaptation, preventing duplicate skill creation.
    Returns (skill_name, parameter_to_pass) or (None, None).
    """
    from modules.skill_engine import list_skills
    clean_action = sanitize_skill_name(action_name)
    existing_skills = list_skills()  # dict of skill_name -> docstring/desc

    # 1. Exact or partial match with registered custom skills in skills/
    for s_name, s_desc in existing_skills.items():
        s_clean = sanitize_skill_name(s_name)
        if clean_action == s_clean or s_clean in clean_action or clean_action in s_clean:
            return s_name, user_input
        if s_desc and (clean_action in s_desc.lower() or any(w in s_desc.lower() for w in clean_action.split('_') if len(w) > 3)):
            return s_name, user_input

    # 2. Parameter mapping to built-in tools
    text = str(user_input).lower()
    if any(w in text for w in ["open app", "launch app", "start app", "run app"]):
        return "open_app", user_input
    if any(w in text for w in ["search web", "google search", "open website", "browse"]):
        return "open_browser", user_input
    if any(w in text for w in ["calculate", "math", "evaluate"]):
        return "python_repl", user_input
    if any(w in text for w in ["read file", "view file", "show content"]):
        return "read_file", user_input

    return None, None


def propose_and_build_skill(action_name, user_input, model_id=None):
    """
    Handle capability gaps: generate, validate, register, and execute skill on approval.
    Includes safeguards to prevent creating duplicate skills or Python scripts for text content generation.
    """
    # Safeguard 1: Text content generation requests should NEVER build Python code skills
    if is_text_content_generation_request(user_input):
        logger.info(f"Skipping skill creation for text content generation request: '{user_input[:50]}...'")
        from modules.rag_context import inject_rag_and_call
        return inject_rag_and_call(user_input, model_id=model_id)

    # Safeguard 2: Check for existing custom skill or tool match to prevent duplicate skill generation
    existing_skill, param = find_existing_matching_skill(action_name, user_input)
    if existing_skill:
        logger.info(f"Reusing existing skill '{existing_skill}' instead of creating duplicate skill.")
        from modules.agent_loop import execute_tool_action
        return execute_tool_action(existing_skill, param)

    clean_name = sanitize_skill_name(action_name)
    print(f"\n⚠️  [Capability Gap]: Jarvis lacks a tool for '{action_name}'.")
    print(f"🔨 [Auto Skill Builder]: Generating custom Python skill for '{clean_name}'...")

    code = generate_skill_code(clean_name, f"Execute user intent: {user_input}", model_id=model_id)
    if not code:
        return f"[ERROR] Could not generate skill code for '{clean_name}'."

    valid, err = validate_skill_code(code)
    if not valid:
        return f"[ERROR] Generated skill code failed validation: {err}"

    print("\n---------------- GENERATED SKILL CODE PREVIEW ----------------")
    print(code[:1000])
    print("--------------------------------------------------------------")

    # Prompt user for approval
    try:
        confirm = input(f"\nApprove registering and executing custom skill '{clean_name}'? (y/n): ").strip().lower()
    except Exception:
        confirm = "n"

    if confirm in ("y", "yes"):
        ok, msg = create_and_register_skill(clean_name, code, description=f"Skill for {user_input}")
        if ok:
            print(f"✅ {msg}")
            return execute_skill(clean_name, input_text=user_input)
        return f"[ERROR] Skill registration failed: {msg}"
    else:
        return f"[CANCELLED] Skill creation for '{clean_name}' was declined by user."
