"""
ReAct Agent Loop Module for HelperBoi / Jarvis
Executes multi-step reasoning and tool-chaining (Thought -> Action -> Action Input -> Observation)
"""

import json
import logging
import re
import os
from modules.llm_client import call_ollama
from modules.model_router import get_llm_model, select_best_model_for_task
from modules.intent_classifier import get_known_intents
from modules import vector_search, code_explain, refactor, polish, summarize, tools_extension
from modules.skill_engine import list_skills, execute_skill

logger = logging.getLogger("jarvis.agent_loop")


def execute_tool_action(action_name, action_input, vault_path=None):
    """
    Execute a tool action by name (built-in or custom skill) and return string observation.
    """
    action_name = action_name.lower().strip()
    input_str = str(action_input).strip()

    try:
        if action_name == "vector_search":
            results = vector_search.search(input_str, top_k=3, vault_path=vault_path, verbose=False)
            return f"Found {len(results)} search results: {results}"
        elif action_name == "summarize":
            return summarize.summarize_note(input_str)
        elif action_name == "polish":
            return polish.polish_note(input_str)
        elif action_name == "code_explain":
            return code_explain.explain_code(input_str)
        elif action_name == "refactor":
            return refactor.refactor_code(input_str)
        elif action_name in ("read_file", "read"):
            return tools_extension.read_file(input_str)
        elif action_name in ("write_file", "write"):
            # Check if input has 'file_path|content' or raw path
            if "|" in input_str:
                parts = input_str.split("|", 1)
                return tools_extension.write_file(parts[0], parts[1])
            return tools_extension.write_file(input_str, "")
        elif action_name in ("python_repl", "eval", "calc", "python"):
            return tools_extension.python_repl(input_str)
        elif action_name in ("diagnose", "system_diagnose", "health"):
            return tools_extension.system_diagnose(vault_path=vault_path)
        elif action_name in ("open_browser", "browser", "google"):
            return tools_extension.open_browser(input_str)
        elif action_name in ("open_app", "launch_app", "app"):
            res = tools_extension.open_app(input_str)
            if "[CAPABILITY_GAP:" in res:
                from modules.skill_builder import propose_and_build_skill
                return propose_and_build_skill(input_str, input_str)
            return res
        elif action_name in list_skills():
            return execute_skill(action_name, input_text=input_str)
        elif os.path.exists(input_str):
            return tools_extension.read_file(input_str)
        else:
            from modules.skill_builder import propose_and_build_skill
            return propose_and_build_skill(action_name, input_str)
    except Exception as e:
        logger.error(f"Tool execution failed for '{action_name}': {e}")
        return f"Error executing tool '{action_name}': {e}"


def run_agent_loop(user_goal, max_iterations=5, model_id=None, vault_path=None):
    """
    Execute a multi-step ReAct loop to achieve a complex goal.
    Returns: Final answer string.
    """
    import sys
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    known_tools = get_known_intents()
    tools_desc = "\n".join([f"- {name}: {desc}" for name, desc in known_tools.items()])

    model_info = get_llm_model(model_id or select_best_model_for_task("refactor", user_goal))

    history = []
    print(f"\n[AGENT] [Jarvis ReAct Loop Started]: \"{user_goal}\"")

    for i in range(1, max_iterations + 1):
        history_str = "\n".join(history)
        prompt = (
            "You are Jarvis, an autonomous AI assistant.\n"
            "Achieve the user's goal by executing tools step-by-step using the ReAct (Reasoning + Acting) format.\n\n"
            "Available Tools:\n"
            f"{tools_desc}\n\n"
            "Format your response EXACTLY as:\n"
            "Thought: <your step-by-step reasoning>\n"
            "Action: <tool_name (or 'Final Answer' when finished)>\n"
            "Action Input: <input string to pass to tool or final response to user>\n\n"
            f"Goal: {user_goal}\n"
            f"Previous Steps:\n{history_str}\n\n"
            f"Step {i} Response:"
        )

        try:
            resp = call_ollama(prompt, endpoint=model_info["endpoint"], model=model_info["model"], timeout=45)
            if resp.startswith("(LLM error"):
                logger.warning(f"Ollama call failed during agent loop step {i}: {resp}")
                return f"Agent loop halted: {resp}"

            print(f"\n--- [Step {i}] ---")
            print(resp.strip())

            # Parse Thought, Action, Action Input
            action_match = re.search(r"Action:\s*(.+)", resp, re.I)
            input_match = re.search(r"Action Input:\s*(.+)", resp, re.I | re.S)

            action = action_match.group(1).strip() if action_match else "Final Answer"
            action_input = input_match.group(1).strip() if input_match else resp.strip()

            if action.lower() == "final answer" or "final answer" in resp.lower():
                print(f"\n[OK] [Goal Achieved]: {action_input}")
                return action_input

            # Execute tool and capture observation
            observation = execute_tool_action(action, action_input, vault_path=vault_path)
            obs_str = f"Observation ({action}): {observation[:1000]}"
            print(f"[OBS] {obs_str}")

            history.append(f"Thought: Executing step {i}\nAction: {action}\nAction Input: {action_input}\n{obs_str}")

        except Exception as e:
            logger.error(f"Error in agent loop iteration {i}: {e}")
            return f"Agent loop encountered error: {e}"

    print("\n[WARN] [Reached Max Iterations limit]")
    return history[-1] if history else "Completed max iterations."
