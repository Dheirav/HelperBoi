import urllib.request
import json
import logging

logger = logging.getLogger("jarvis.model_router")

LLM_MODELS = [
    {
        "name": "LLaMA 3 8B",
        "id": "llama3",
        "model": "llama3:latest",
        "endpoint": "http://localhost:11434",
        "type": "ollama",
        "description": "General conversation, intent classification & smart context (default)",
        "ram": "~4.7 GB VRAM",
        "default": True
    },
    {
        "name": "LLaMA 3.2",
        "id": "llama3.2",
        "model": "llama3.2:latest",
        "endpoint": "http://localhost:11434",
        "type": "ollama",
        "description": "Fast lightweight LLM model",
        "ram": "~2.0 GB VRAM"
    },
    {
        "name": "Mistral 7B",
        "id": "mistral",
        "model": "mistral:latest",
        "endpoint": "http://localhost:11434",
        "type": "ollama",
        "description": "General conversation and reasoning",
        "ram": "~4.1 GB VRAM"
    },
    {
        "name": "CodeLLaMA 7B",
        "id": "codellama",
        "model": "codellama:latest",
        "endpoint": "http://localhost:11434",
        "type": "ollama",
        "description": "Code generation & refactoring",
        "ram": "~4.7 GB VRAM"
    },
    {
        "name": "Qwen 2.5 Coder 7B",
        "id": "qwen2.5-coder:7b",
        "model": "qwen2.5-coder:7b",
        "endpoint": "http://localhost:11434",
        "type": "ollama",
        "description": "Fast code generation & function calling",
        "ram": "~4.7 GB VRAM"
    }
]

_INSTALLED_MODELS_CACHE = None

def get_installed_ollama_models():
    """Dynamically query Ollama API for currently installed model tags."""
    global _INSTALLED_MODELS_CACHE
    if _INSTALLED_MODELS_CACHE is not None:
        return _INSTALLED_MODELS_CACHE
    try:
        req = urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        data = json.loads(req.read().decode())
        _INSTALLED_MODELS_CACHE = [m["name"] for m in data.get("models", [])]
        return _INSTALLED_MODELS_CACHE
    except Exception as e:
        logger.warning(f"Could not query Ollama installed models: {e}")
        return []


def get_llm_model(model_id=None):
    """Retrieve model configuration dictionary by ID or model name, falling back to installed models."""
    if model_id is not None and not isinstance(model_id, str):
        raise TypeError(f"model_id must be a string, got {type(model_id).__name__}")

    installed = get_installed_ollama_models()

    # 1. Direct match requested model_id
    if model_id:
        for m in LLM_MODELS:
            if m["id"] == model_id or m["model"] == model_id or m["id"].split(":")[0] == model_id:
                if not installed or m["model"] in installed:
                    return m

    # 2. Check default model
    for m in LLM_MODELS:
        if m.get("default") and (not installed or m["model"] in installed):
            return m

    # 3. Match any model present in installed list
    if installed:
        first_installed = installed[0]
        for m in LLM_MODELS:
            if m["model"] == first_installed:
                return m
        # Create dynamic entry for first installed model
        return {
            "name": first_installed,
            "id": first_installed,
            "model": first_installed,
            "endpoint": "http://localhost:11434",
            "type": "ollama",
            "description": "Dynamically detected local Ollama model",
            "ram": "Unknown"
        }

    return LLM_MODELS[0]


def select_best_model_for_task(task, prompt=None):
    """
    Given a task/command and optional prompt, return the best model id for the job.
    """
    task = task.lower()

    if task in ["code_explain", "refactor"]:
        return "qwen2.5-coder:7b"

    if prompt:
        if any(w in prompt.lower() for w in ["code", "function", "class", "python", "refactor"]):
            return "qwen2.5-coder:7b"
        if any(w in prompt.lower() for w in ["summarize", "summary", "polish"]):
            return "qwen2.5-coder:7b"

    installed = get_installed_ollama_models()
    if installed and "llama3:latest" in installed:
        return "llama3"
    if installed and "llama3.2:latest" in installed:
        return "llama3.2"
    if installed and "mistral:latest" in installed:
        return "mistral"

    return "llama3"


def pull_ollama_model(model_tag):
    """Pull/download a new LLM model into local Ollama installation."""
    import subprocess
    global _INSTALLED_MODELS_CACHE
    tag = str(model_tag).strip()
    try:
        proc = subprocess.run(["ollama", "pull", tag], capture_output=True, text=True, check=True)
        _INSTALLED_MODELS_CACHE = None  # Reset cache
        return f"[SUCCESS] Successfully pulled model '{tag}'!\n{proc.stdout.strip()}"
    except Exception as e:
        return f"[ERROR] Failed to pull model '{tag}': {e}"


def delete_ollama_model(model_tag):
    """Delete/remove an unwanted or redundant LLM model from Ollama."""
    import subprocess
    global _INSTALLED_MODELS_CACHE
    tag = str(model_tag).strip()
    try:
        proc = subprocess.run(["ollama", "rm", tag], capture_output=True, text=True, check=True)
        _INSTALLED_MODELS_CACHE = None  # Reset cache
        return f"[SUCCESS] Successfully deleted model '{tag}'.\n{proc.stdout.strip()}"
    except Exception as e:
        return f"[ERROR] Failed to delete model '{tag}': {e}"



