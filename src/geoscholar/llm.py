"""Minimal client for a local Ollama server."""
import requests

from geoscholar import config


def chat_full(prompt, system=None, temperature=0.1, json_mode=False, model=None,
              num_ctx=config.LLM_NUM_CTX, timeout=300):
    """Send one prompt; return the reply plus Ollama's token counts and timings."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = {
        "model": model or config.LLM_MODEL,
        "messages": messages,
        "stream": False,
        # num_ctx: Ollama's context window. If the prompt is longer, Ollama silently
        # drops the beginning of it, so we set it explicitly.
        "options": {"temperature": temperature, "num_ctx": num_ctx},
    }
    if json_mode:
        body["format"] = "json"
    resp = requests.post(f"{config.OLLAMA_URL}/api/chat", json=body, timeout=timeout)
    if not resp.ok:
        raise RuntimeError(f"Ollama error {resp.status_code}: {resp.text}")
    data = resp.json()
    eval_s = data.get("eval_duration", 0) / 1e9            # Ollama reports nanoseconds
    return {
        "content": data["message"]["content"],
        "prompt_tokens": data.get("prompt_eval_count"),
        "output_tokens": data.get("eval_count"),
        "load_s": data.get("load_duration", 0) / 1e9,
        "total_s": data.get("total_duration", 0) / 1e9,
        "tokens_per_s": (data.get("eval_count", 0) / eval_s) if eval_s else None,
    }


def chat(prompt, system=None, temperature=0.1, json_mode=False, model=None, **kwargs):
    """Send one prompt and return just the reply text."""
    return chat_full(prompt, system=system, temperature=temperature,
                     json_mode=json_mode, model=model, **kwargs)["content"]