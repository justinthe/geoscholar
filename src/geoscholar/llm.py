"""Minimal client for a local Ollama server."""
import json

import requests

from geoscholar import config


def _body(prompt, system, temperature, json_mode, model, num_ctx, stream):
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = {
        "model": model or config.LLM_MODEL,
        "messages": messages,
        "stream": stream,
        # num_ctx: Ollama's context window. If the prompt is longer, Ollama silently
        # drops the beginning of it, so we set it explicitly.
        "options": {"temperature": temperature, "num_ctx": num_ctx},
    }
    if json_mode:
        body["format"] = "json"
    return body


def _stats(data):
    eval_s = data.get("eval_duration", 0) / 1e9            # Ollama reports nanoseconds
    return {
        "prompt_tokens": data.get("prompt_eval_count"),
        "output_tokens": data.get("eval_count"),
        "load_s": data.get("load_duration", 0) / 1e9,
        "total_s": data.get("total_duration", 0) / 1e9,
        "tokens_per_s": (data.get("eval_count", 0) / eval_s) if eval_s else None,
    }


def chat_full(prompt, system=None, temperature=0.1, json_mode=False, model=None,
              num_ctx=config.LLM_NUM_CTX, timeout=300):
    """Send one prompt; return the reply plus Ollama's token counts and timings."""
    resp = requests.post(f"{config.OLLAMA_URL}/api/chat", timeout=timeout,
                         json=_body(prompt, system, temperature, json_mode, model, num_ctx, False))
    if not resp.ok:
        raise RuntimeError(f"Ollama error {resp.status_code}: {resp.text}")
    data = resp.json()
    return {"content": data["message"]["content"], **_stats(data)}


def chat(prompt, system=None, temperature=0.1, json_mode=False, model=None, **kwargs):
    """Send one prompt and return just the reply text."""
    return chat_full(prompt, system=system, temperature=temperature,
                     json_mode=json_mode, model=model, **kwargs)["content"]


def chat_stream(prompt, system=None, temperature=0.1, model=None,
                num_ctx=config.LLM_NUM_CTX, timeout=300):
    """Yield ("token", text) pieces as the model writes, then one ("stats", dict) at the end.

    With stream=True, Ollama sends one JSON object per line; the last has "done": true
    and carries the token counts.
    """
    with requests.post(f"{config.OLLAMA_URL}/api/chat", stream=True, timeout=timeout,
                       json=_body(prompt, system, temperature, False, model, num_ctx, True)) as resp:
        if not resp.ok:
            raise RuntimeError(f"Ollama error {resp.status_code}: {resp.text}")
        for line in resp.iter_lines():
            if not line:
                continue
            data = json.loads(line)
            if "error" in data:
                raise RuntimeError(f"Ollama error: {data['error']}")
            piece = data.get("message", {}).get("content", "")
            if piece:
                yield "token", piece
            if data.get("done"):
                yield "stats", _stats(data)
                return


def ollama_ok(timeout=3):
    """True if the Ollama server answers and has the configured model."""
    try:
        resp = requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=timeout)
        names = [m.get("name", "") for m in resp.json().get("models", [])]
        return resp.ok and any(n == config.LLM_MODEL or n.split(":")[0] == config.LLM_MODEL for n in names)
    except Exception:
        return False