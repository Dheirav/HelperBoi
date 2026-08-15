"""Shared Ollama client utilities and exception definitions used across modules."""

import logging
import time
import requests

logger = logging.getLogger("jarvis.llm_client")

class LLMError(Exception):
    """Base exception for all LLM errors."""
    pass

class LLMConnectionError(LLMError):
    """Raised when connection to LLM backend fails."""
    pass

class LLMTimeoutError(LLMError):
    """Raised when LLM request times out."""
    pass

class LLMAPIError(LLMError):
    """Raised when LLM backend returns an HTTP error status."""
    def __init__(self, status_code, message):
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code
        self.message = message


def compute_dynamic_timeout(prompt, base_timeout=30, per_500_chars=10, max_timeout=600):
    """Scale timeout by prompt length with sane caps."""
    extra_timeout = max(0, (len(prompt) // 500) * per_500_chars)
    return min(base_timeout + extra_timeout, max_timeout)


def call_ollama(prompt, endpoint, model, timeout=None, debug=False, raise_on_error=False):
    """Send a non-streaming prompt to Ollama and return response text or error string."""
    url = f"{endpoint}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }

    timeout = timeout if timeout is not None else compute_dynamic_timeout(prompt)
    start_time = time.time()

    if debug:
        logger.debug(f"Prompt length: {len(prompt)} chars | Timeout: {timeout}s")
        print(f"[DEBUG] Prompt length: {len(prompt)} chars | Timeout: {timeout}s")

    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        elapsed = time.time() - start_time
        if debug:
            logger.debug(f"LLM request took {elapsed:.2f} seconds.")
            print(f"[DEBUG] LLM request took {elapsed:.2f} seconds.")

        if resp.status_code >= 400:
            try:
                err = resp.json().get("error", resp.text)
            except Exception:
                err = resp.text
            msg = f"HTTP {resp.status_code}: {err}"
            logger.error(f"LLM API error: {msg}")
            if raise_on_error:
                raise LLMAPIError(resp.status_code, err)
            return f"(LLM error: {msg})"

        data = resp.json()
        return data.get("response", "(No response from LLM)")
    except requests.exceptions.Timeout as e:
        elapsed = time.time() - start_time
        logger.error(f"LLM request timed out after {elapsed:.2f}s: {e}")
        if raise_on_error:
            raise LLMTimeoutError(f"Request timed out after {timeout}s") from e
        return f"(LLM error: Timed out after {timeout}s | {e})"
    except requests.exceptions.RequestException as e:
        elapsed = time.time() - start_time
        logger.error(f"LLM request failed after {elapsed:.2f}s: {e}")
        if raise_on_error:
            raise LLMConnectionError(f"Connection failed: {e}") from e
        return f"(LLM error: {e} | Used timeout: {timeout}s)"