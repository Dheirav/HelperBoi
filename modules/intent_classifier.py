"""
Intent Classifier Module for HelperBoi / Jarvis
Parses free-form natural language user input into structured JSON intents, target files, and parameters.
"""

import json
import logging
import re
from modules.llm_client import call_ollama
from modules.model_router import get_llm_model, select_best_model_for_task

logger = logging.getLogger("jarvis.intent_classifier")

BUILTIN_INTENTS = {
    "polish": "Polish, clean up grammar, format, or improve readability of a note or text snippet.",
    "summarize": "Summarize a note, document, or text snippet in short, medium, or detailed format.",
    "smartlink": "Suggest [[wikilinks]], backlinks, tags, or split a note into atomic Zettelkasten notes.",
    "code_explain": "Explain code, functions, algorithms, or programming logic from a file or text.",
    "refactor": "Refactor, optimize, clean up, or reformat code or notes.",
    "context_note": "Generate a new context-aware note based on existing vault notes.",
    "vector_search": "Perform semantic search over Obsidian notes or documents for a topic or query.",
    "analyze_notes": "Analyze vault notes for writing style, note types, statistics, and topics.",
    "backup": "Run Git backup of the vault.",
    "python_repl": "Safely execute Python math calculations, logic evaluation, or script snippets.",
    "read_file": "Read file contents from allowed directories.",
    "write_file": "Write content to a file in allowed directories.",
    "open_browser": "Open default web browser to a URL, web service like Gmail/YouTube/GitHub, or Google search query.",
    "open_app": "Launch a locally installed Windows desktop application like WhatsApp, Spotify, Discord, Telegram, Zoom, Teams, etc.",
    "diagnose": "Run full system diagnostic health audit (CPU, RAM, VRAM, Ollama, Vault, Git).",
    "remember": "Learn or save a new user preference or natural language instruction.",
    "prefs": "View or update user preferences.",
    "general_chat": "General question, conversation, or greeting not matching specific tools."
}


def get_known_intents():
    """Return dictionary of known intents including built-in tools and custom skills."""
    intents = dict(BUILTIN_INTENTS)
    try:
        import os
        skills_dir = os.path.join(os.path.dirname(__file__), '..', 'skills')
        if os.path.exists(skills_dir):
            for item in os.listdir(skills_dir):
                skill_path = os.path.join(skills_dir, item)
                if os.path.isdir(skill_path):
                    doc_file = os.path.join(skill_path, 'SKILL.md')
                    if os.path.exists(doc_file):
                        with open(doc_file, 'r', encoding='utf-8', errors='ignore') as f:
                            intents[item] = f.read()[:200].replace('\n', ' ')
    except Exception as e:
        logger.warning(f"Could not load custom skills for intent index: {e}")
    return intents


def build_classification_prompt(user_input, known_intents):
    """Format system prompt for qwen2.5-coder to return strict JSON intent classification."""
    intent_descriptions = "\n".join([f"- {name}: {desc}" for name, desc in known_intents.items()])
    prompt = (
        "You are the Intent Classifier for Jarvis AI Assistant.\n"
        "Classify the following user input into ONE of the available intents and extract relevant parameters.\n\n"
        "Available Intents:\n"
        f"{intent_descriptions}\n\n"
        "Output ONLY a valid JSON object with the following structure (no markdown formatting, no extra text):\n"
        "{\n"
        '  "intent": "<intent_name>",\n'
        '  "confidence": <float between 0.0 and 1.0>,\n'
        '  "target_file": "<extracted file path or null>",\n'
        '  "params": {\n'
        '    "level": "<short|medium|detailed if summarize, else null>",\n'
        '    "query": "<search query string if vector_search, else null>",\n'
        '    "target": "<extracted URL or site name like gmail, youtube, google if open_browser, else null>",\n'
        '    "app_name": "<name of desktop app to launch if open_app, e.g. whatsapp, spotify, discord, else null>",\n'
        '    "instruction": "<custom instruction if relevant, else null>"\n'
        '  }\n'
        "}\n\n"
        f"User Input: \"{user_input}\"\n"
        "JSON Response:"
    )
    return prompt


def classify_intent(user_input, model_id=None):
    """
    Classify free-form user input into structured JSON intent dictionary.
    Returns: dict with keys 'intent', 'confidence', 'target_file', 'params'.
    """
    cleaned_input = user_input.strip()
    if not cleaned_input:
        return {
            "intent": "general_chat",
            "confidence": 1.0,
            "target_file": None,
            "params": {}
        }

    # Fast heuristic checks for direct utility keywords & aliases
    lower_input = cleaned_input.lower()
    first_word = lower_input.split()[0]
    
    ALIAS_MAP = {
        "pref": "prefs",
        "prefs": "prefs",
        "stat": "status",
        "stats": "status",
        "status": "status",
        "sys": "status",
        "system": "status",
        "hist": "history",
        "history": "history",
        "models": "model",
        "model": "model",
        "h": "help",
        "help": "help",
        "q": "q",
        "quit": "quit",
        "exit": "exit",
        "clear": "clear",
        "cls": "clear",
        "approve": "approve",
        "gaming": "gaming",
        "resume": "resume",
        "low-power": "low-power",
        "mode": "mode",
        "dry-run": "dry-run",
        "autostart": "autostart",
        "google": "open_browser",
        "browser": "open_browser",
        "open_browser": "open_browser",
        "task_log": "task_log",
        "feature_registry": "feature_registry",
        "frequent": "frequent"
    }
    
    words = lower_input.split()
    # Single-word command shortcuts (e.g. 'cls', 'help', 'exit') ONLY match if input is exactly 1 word
    if len(words) == 1 and words[0] in ALIAS_MAP:
        return {
            "intent": ALIAS_MAP[words[0]],
            "confidence": 1.0,
            "target_file": None,
            "params": {}
        }

    # Instant Heuristic Pre-Pass: If rule-based classifier is highly confident (>= 0.8), use it immediately!
    fast_result = fallback_classification(cleaned_input)
    if fast_result.get("confidence", 0.0) >= 0.8:
        return fast_result

    known_intents = get_known_intents()
    prompt = build_classification_prompt(cleaned_input, known_intents)
    model_info = get_llm_model(model_id or select_best_model_for_task("polish", cleaned_input))

    try:
        raw_response = call_ollama(prompt, endpoint=model_info["endpoint"], model=model_info["model"], timeout=15)
        if raw_response.startswith("(LLM error"):
            logger.warning(f"Ollama call failed during intent classification: {raw_response}")
            return fallback_classification(cleaned_input)

        # Clean JSON markdown fences if LLM includes them
        cleaned_json = raw_response.strip()
        cleaned_json = re.sub(r"^```json\s*", "", cleaned_json, flags=re.I)
        cleaned_json = re.sub(r"^```\s*", "", cleaned_json)
        cleaned_json = re.sub(r"\s*```$", "", cleaned_json)

        try:
            data = json.loads(cleaned_json)
        except Exception:
            # Fix trailing commas or extract intent via regex if JSON syntax is slightly malformed
            repaired = re.sub(r',\s*([\}\]])', r'\1', cleaned_json)
            match_intent = re.search(r'"intent"\s*:\s*"([^"]+)"', cleaned_json)
            if match_intent and match_intent.group(1).lower() in known_intents:
                data = {"intent": match_intent.group(1).lower(), "confidence": 0.7, "target_file": None, "params": {}}
            else:
                data = json.loads(repaired)

        if "intent" in data and data["intent"] in known_intents:
            return data
    except Exception as e:
        logger.warning(f"JSON parsing failed for intent classification: {e}")

    return fallback_classification(cleaned_input)


def fallback_classification(user_input):
    """Rule-based fallback intent classification when LLM is unavailable or output is malformed."""
    text = user_input.lower()
    # Check for multi-step conjunctions
    if any(conj in text for conj in [" and then ", " then ", " and also ", " and summarize", " and refactor", " and polish"]):
        return {"intent": "multi_step_chain", "confidence": 0.9, "target_file": extract_filepath(user_input), "params": {}}
    if any(w in text for w in ["polish", "clean", "grammar", "formatting", "fix text"]):
        return {"intent": "polish", "confidence": 0.8, "target_file": extract_filepath(user_input), "params": {}}
    if any(w in text for w in ["summarize", "summary", "brief", "shorten"]):
        level = "short" if "short" in text else "detailed" if "detail" in text else "medium"
        return {"intent": "summarize", "confidence": 0.8, "target_file": extract_filepath(user_input), "params": {"level": level}}
    if any(w in text for w in ["explain code", "explain", "how code works"]):
        return {"intent": "code_explain", "confidence": 0.8, "target_file": extract_filepath(user_input), "params": {}}
    if any(w in text for w in ["refactor", "optimize code", "restructure"]):
        return {"intent": "refactor", "confidence": 0.8, "target_file": extract_filepath(user_input), "params": {}}
    if any(w in text for w in ["search", "find", "semantic"]):
        return {"intent": "vector_search", "confidence": 0.8, "target_file": None, "params": {"query": user_input}}

    if any(w in text for w in ["link", "wikilink", "atomic", "zettel"]):
        return {"intent": "smartlink", "confidence": 0.8, "target_file": extract_filepath(user_input), "params": {}}
    if any(w in text for w in ["analyze", "vault stats", "writing style"]):
        return {"intent": "analyze_notes", "confidence": 0.8, "target_file": None, "params": {}}
    if any(w in text for w in ["backup", "git backup"]):
        return {"intent": "backup", "confidence": 0.8, "target_file": None, "params": {}}
    if "import" in text and any(w in text for w in ["contact", "vcf", "csv"]):
        f_path = extract_filepath(user_input) or user_input.split()[-1]
        return {"intent": "import_contacts", "confidence": 0.95, "target_file": f_path, "params": {"file_path": f_path}}
    # Detect in-app sub-actions BEFORE simple app launch
    # E.g. "open the chat Nivedita in WhatsApp" -> in_app_action, not open_app
    in_app = detect_in_app_action(user_input)
    if in_app:
        return in_app

    # Dynamic desktop app or application launcher intent (simple "open X")
    if any(w in text for w in ["open", "launch", "start", "run"]):
        # Check if browser/url/search is explicitly requested
        if not any(w in text for w in ["browser", "website", "url", "http", "www", "google", "search"]):
            target_app = extract_intent_target(user_input)
            if target_app:
                return {"intent": "open_app", "confidence": 0.9, "target_file": None, "params": {"app_name": target_app}}

    if any(w in text for w in ["open google", "open browser", "open gmail", "open youtube", "open github", "browse", "gmail", "youtube", "github"]):
        target = "gmail" if "gmail" in text or "mail" in text else "youtube" if "youtube" in text else "github" if "github" in text else "google"
        return {"intent": "open_browser", "confidence": 0.9, "target_file": None, "params": {"target": target}}

    return {"intent": "general_chat", "confidence": 0.5, "target_file": None, "params": {"instruction": user_input}}


def extract_filepath(text):
    """Heuristic extractor for file paths mentioned in text."""
    match = re.search(r'[\w\-\\/\.:]+\.(md|py|txt|json|csv)', text, re.I)
    return match.group(0) if match else None


def extract_intent_target(text):
    """
    Dynamically extract target application or action subject from natural language.
    Examples:
    - 'can you open my WhatsApp app and not the browser' -> 'whatsapp'
    - 'launch Spotify' -> 'spotify'
    - 'open visual studio code' -> 'visual studio code'
    """
    clean = str(text).strip()
    match = re.search(r'\b(open|launch|start|run)\b(?:\s+(?:my|the|a|an))?(?:\s+(?:app|application|program))?\s+([a-z0-9\s\-_]+)', clean, re.I)
    if match:
        target = match.group(2).strip()
        # Clean trailing phrases
        target = re.sub(r'\s+(app|application|program|and not.*|in browser|on web)$', '', target, flags=re.I).strip()
        return target
    return clean


def detect_in_app_action(text):
    """
    Detect sub-actions WITHIN an app, distinguishing them from simple 'open app' commands.
    Returns structured intent dict if detected, None otherwise.
    
    Examples:
    - 'open the chat Nivedita in WhatsApp' -> in_app_action(app=whatsapp, sub_action=open_chat, target=Nivedita)
    - 'play Blinding Lights on Spotify' -> in_app_action(app=spotify, sub_action=play, target=Blinding Lights)
    - 'send a message to John on Telegram' -> in_app_action(app=telegram, sub_action=send_message, target=John)
    - 'open WhatsApp' -> None (simple app launch, not a sub-action)
    """
    clean = str(text).strip()
    text_lower = clean.lower()

    # Pattern 1: "<action> <thing> in/on <app>"
    # e.g. "open the chat Nivedita in WhatsApp", "play song X on Spotify"
    match = re.search(
        r'\b(open|send|play|call|message|chat|search|find|go to|navigate to)\b'
        r'\s+(?:the\s+|a\s+|my\s+)?'
        r'(?:chat|message|song|track|playlist|video|contact|conversation|call|file|group)?\s*'
        r'(.+?)\s+(?:in|on|via|through|using)\s+(\w+)\s*$',
        clean, re.I
    )
    if match:
        sub_action = match.group(1).strip().lower()
        target = match.group(2).strip()
        app_name = match.group(3).strip().lower()
        return {
            "intent": "in_app_action",
            "confidence": 0.95,
            "target_file": None,
            "params": {
                "app_name": app_name,
                "sub_action": sub_action,
                "target": target
            }
        }

    # Pattern 2: "<action> <person> on/in <app>"
    # e.g. "message John on WhatsApp", "call Mom on Telegram"
    match2 = re.search(
        r'\b(message|call|text|ping|dm)\b\s+(.+?)\s+(?:on|in|via|through)\s+(\w+)\s*$',
        clean, re.I
    )
    if match2:
        sub_action = match2.group(1).strip().lower()
        target = match2.group(2).strip()
        app_name = match2.group(3).strip().lower()
        return {
            "intent": "in_app_action",
            "confidence": 0.95,
            "target_file": None,
            "params": {
                "app_name": app_name,
                "sub_action": sub_action,
                "target": target
            }
        }

    # Pattern 3: "open (the|my)? <app> chat (of|with|for|to) <target>"
    # e.g. "open the whatsapp chat of 7358114173", "open whatsapp chat with Niveditha"
    match3 = re.search(
        r'\b(open|start|launch)\b\s+(?:the\s+|a\s+|my\s+)?(\w+)\s+(?:chat|message|conversation)\s+(?:of|with|for|to)\s+(.+?)\s*$',
        clean, re.I
    )
    if match3:
        sub_action = match3.group(1).strip().lower()
        app_name = match3.group(2).strip().lower()
        target = match3.group(3).strip()
        return {
            "intent": "in_app_action",
            "confidence": 0.95,
            "target_file": None,
            "params": {
                "app_name": app_name,
                "sub_action": sub_action,
                "target": target
            }
        }

    return None

