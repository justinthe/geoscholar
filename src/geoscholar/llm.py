"""Minimal client for a local Ollama server."""
import requests

from geoscholar import config


def chat(prompt, system=None, temperature=0.1, json_mode=False, model=None, timeout=300):
    """Send one prompt and return the model's reply as a string.

    json_mode=True asks Ollama to constrain the output to valid JSON.
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = {
        "model": model or config.LLM_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if json_mode:
        body["format"] = "json"
    resp = requests.post(f"{config.OLLAMA_URL}/api/chat", json=body, timeout=timeout)
    if not resp.ok:
        raise RuntimeError(f"Ollama error {resp.status_code}: {resp.text}")
    return resp.json()["message"]["content"]