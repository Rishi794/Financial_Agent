from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from typing import Any


def _clip(text: str, limit: int = 16000) -> str:
    return text if len(text) <= limit else text[:limit] + "\n...[truncated]"


def chat(messages: list[dict[str, str]], max_tokens: int, temperature: float) -> str:
    base = "http://127.0.0.1:8080/v1"
    payload = {
        "model": "Qwen3.5-4B-Q4_K_M",
        "messages": messages,
        "temperature": temperature,
        "top_p": 0.8,
        "max_tokens": max_tokens,
        "stream": False,
    }
    req = urllib.request.Request(
        base + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    last: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=360) as r:
                data = json.loads(r.read().decode())
            content = data["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise RuntimeError(f"empty llama.cpp response: {data}")
            return _clip(content)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, KeyError, json.JSONDecodeError, RuntimeError) as exc:
            last = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"llama.cpp request failed after retries: {last}")


def extract_json(text: str) -> dict[str, Any]:
    candidates = [text.strip()]
    candidates += re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.I | re.S)
    for start in [m.start() for m in re.finditer(r"\{", text)]:
        depth = 0
        in_str = False
        escaped = False
        for i in range(start, len(text)):
            c = text[i]
            if in_str:
                if escaped:
                    escaped = False
                elif c == "\\":
                    escaped = True
                elif c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        candidates.append(text[start:i + 1])
                        break
    for candidate in candidates:
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict) and obj.get("type") in {"tool", "final"}:
                return obj
        except json.JSONDecodeError:
            pass
    raise ValueError("No valid agent JSON object found")
