"""DET-2: ask the local Ollama model for the tactic check (prd C4).

Guardrail 2: this file never imports a network library. The HTTP call goes
through `callguard.server.egress.local_ollama_post()` (SRV-3), which only
accepts localhost. Tests and the eval can pass their own `post` callable.
Guardrail 5: localhost Ollama only; never a cloud model.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Callable

OLLAMA_URL = "http://localhost:11434/api/chat"
DEFAULT_MODEL = "qwen2.5:7b"
TIMEOUT_S = 8.0
# prompt.md is ~1.1k tokens; 30 s of speech is ~100 tokens. 4096 leaves room.
NUM_CTX = 4096
# Caps generation so a rambling answer can't blow the latency budget. A full
# danger answer (4-5 evidence items) is ~250 tokens; too low truncates the JSON.
NUM_PREDICT = 512
KEEP_ALIVE = "60m"  # keep the model loaded so the demo never waits for a reload

PROMPT_PATH = Path(__file__).with_name("prompt.md")

Post = Callable[..., dict]  # post(url, payload, timeout=...) -> parsed JSON reply


class OllamaError(Exception):
    """The model call failed. The message never contains transcript text."""


def model_name() -> str:
    return os.environ.get("CALLGUARD_MODEL", "").strip() or DEFAULT_MODEL


@lru_cache(maxsize=1)
def system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def build_payload(window_text: str, model: str | None = None) -> dict:
    return {
        "model": model or model_name(),
        "stream": False,
        "format": "json",
        "keep_alive": KEEP_ALIVE,
        "options": {"temperature": 0, "num_ctx": NUM_CTX, "num_predict": NUM_PREDICT},
        "messages": [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": "Transcript (last 30 seconds):\n" + window_text},
        ],
    }


def _default_post() -> Post:
    try:
        from callguard.server.egress import local_ollama_post
    except Exception as e:  # Server lane not merged yet, or httpx missing
        raise OllamaError(f"no local model transport ({type(e).__name__})") from None
    return local_ollama_post


def chat(window_text: str, post: Post | None = None, model: str | None = None,
         timeout: float = TIMEOUT_S) -> str:
    """Send the window to the model and return its raw reply text (JSON, unparsed).

    Raises OllamaError on any failure; `check()` turns that into a fallback.
    """
    send = post or _default_post()
    try:
        reply = send(OLLAMA_URL, build_payload(window_text, model), timeout=timeout)
    except Exception as e:
        raise OllamaError(f"model call failed ({type(e).__name__})") from None
    content = (reply.get("message") or {}).get("content") if isinstance(reply, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise OllamaError("model reply had no content")
    return content
