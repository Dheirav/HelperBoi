import sys
import importlib
import ast
from modules.llm_client import call_ollama as shared_call_ollama

from modules.model_router import get_llm_model as router_get_llm_model

def get_llm_model(model_id=None):
    """Retrieve model info from model_router and check availability in Ollama. Fallback to 'mistral' if unavailable."""
    model_info = router_get_llm_model(model_id)
    # Check if the model is available in Ollama
    try:
        import requests
        endpoint = model_info.get("endpoint", "http://localhost:11434")
        model_name = model_info.get("model", "")
        model_base = model_name.split(":")[0]  # Base model name e.g. 'mistral'
        resp = requests.get(f"{endpoint}/api/tags", timeout=5)
        if resp.status_code == 200:
            tags = resp.json().get("models", [])
            available_models = [m.get("name", "") for m in tags]
            available_bases = [m.split(":")[0] for m in available_models]
            print(f"[DEBUG] Ollama available models: {available_models}")
            if not available_models or (model_name not in available_models and model_base not in available_bases):
                print(f"[DEBUG] Model '{model_name}' not available in Ollama. Falling back to 'mistral'.")
                fallback = model_info.copy()
                fallback["model"] = "mistral"
                return fallback
    except Exception as e:
        print(f"[DEBUG] Could not check Ollama models: {e}")
        fallback = model_info.copy()
        fallback["model"] = "mistral"
        return fallback
    return model_info


def code_explain_llm(code, model_info):
    if not code.strip():
        return "(No code to explain)"
    prompt = f"Explain the following code in detail:\n{code.strip()}"
    timeout = 120 if "codellama" in str(model_info.get("model", "")).lower() else 60
    print(f"[DEBUG] Calling Ollama at {model_info['endpoint']}/api/generate with model '{model_info['model']}'")
    return shared_call_ollama(prompt, endpoint=model_info["endpoint"], model=model_info["model"], timeout=timeout)


def _local_code_explain(code):
    """Heuristic fallback explanation when LLM is unavailable."""
    code = code.strip()
    if not code:
        return "(No code to explain)"

    lines = [ln for ln in code.splitlines() if ln.strip()]
    summary = []

    try:
        tree = ast.parse(code)
        fn_names = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        cls_names = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        if fn_names:
            summary.append(f"Defines function(s): {', '.join(fn_names)}.")
        if cls_names:
            summary.append(f"Defines class(es): {', '.join(cls_names)}.")
    except Exception:
        pass

    preview = lines[0][:120] if lines else ""
    if preview:
        summary.append(f"Code preview: {preview}")
    summary.append("LLM backend unavailable or model missing, so this is a local heuristic explanation.")
    return " ".join(summary)

def explain_code(code, model_id=None):
    """Explain code using selected/default LLM model with robust fallback behavior."""
    if model_id is None:
        from modules.model_router import select_best_model_for_task
        selected_model_id = select_best_model_for_task("code_explain", code)
    else:
        selected_model_id = model_id

    # Try requested model first, then known safe fallback model.
    tried = []
    for candidate in [selected_model_id, "mistral"]:
        if candidate in tried:
            continue
        tried.append(candidate)
        model_info = get_llm_model(candidate)
        print(f"[DEBUG] model_info: {model_info}")
        result = code_explain_llm(code, model_info)
        if not result.startswith("(LLM error"):
            return result
        print(f"[DEBUG] LLM attempt failed for model '{model_info.get('model')}': {result}")

    return _local_code_explain(code)
