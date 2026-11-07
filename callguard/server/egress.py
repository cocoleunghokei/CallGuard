"""SRV-3: the ONLY module in Callguard that touches the network (guardrail 2).

- search(org): the one cloud call. An EgressEntry is recorded in memory BEFORE
  the request goes out, then given its final status and pushed to listeners
  (the WebSocket `egress` message). Offline or failing searches return a status,
  they never raise. SRV-8 adds safe_org(), Exa fallback, phone extraction, cache.
- online(): reachability probe for status.online (C16). It opens a TCP
  connection to the search host and closes it without sending a byte, so it is
  not an egress entry (nothing leaves the device). Cached for 15 s.
- local_ollama_post(): Detection's path to Ollama. Only localhost; not logged
  as egress because nothing leaves the device.

Nothing from a transcript is ever passed in here except a claimed org name.
"""
from __future__ import annotations

import logging
import os
import re
import socket
import threading
import time
from datetime import datetime
from typing import Any, Callable
from urllib.parse import urlsplit

import httpx

from callguard.shared.contracts import EgressEntry, Verify

log = logging.getLogger("callguard.server.egress")

TAVILY_HOST = "api.tavily.com"
TAVILY_URL = f"https://{TAVILY_HOST}/search"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
MAX_QUERY_CHARS = 80
SEARCH_TIMEOUT_S = 6.0
ONLINE_CACHE_S = 15.0

# Test seam: an httpx transport (e.g. httpx.MockTransport). None = real network.
_transport: httpx.BaseTransport | None = None

_lock = threading.Lock()
entries: list[EgressEntry] = []  # the egress log, in memory only
_listeners: list[Callable[[EgressEntry], None]] = []
_online_cache: tuple[float, bool] | None = None


class LocalModelError(Exception):
    """Ollama on localhost could not be reached or returned an error."""


# ---------------------------------------------------------------- egress log
def subscribe(fn: Callable[[EgressEntry], None]) -> None:
    _listeners.append(fn)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _new_entry(destination: str, sent: str, status: str) -> EgressEntry:
    entry: EgressEntry = {"time": _now(), "destination": destination, "sent": sent, "status": status}  # type: ignore[typeddict-item]
    with _lock:
        entries.append(entry)
    return entry


def _publish(entry: EgressEntry) -> None:
    for fn in list(_listeners):
        try:
            fn(dict(entry))  # type: ignore[arg-type]
        except Exception:
            log.exception("egress listener failed")


def record_refused(destination: str = TAVILY_HOST) -> EgressEntry:
    """A lookup we refused to make: nothing sent, `sent` is empty."""
    entry = _new_entry(destination, "", "refused")
    _publish(entry)
    return entry


# ---------------------------------------------------------------- online probe
def _probe(host: str = TAVILY_HOST, port: int = 443, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def online(force: bool = False) -> bool:
    """True if the search host is reachable. CALLGUARD_OFFLINE=1 forces False."""
    global _online_cache
    if os.environ.get("CALLGUARD_OFFLINE") == "1":
        return False
    now = time.monotonic()
    if not force and _online_cache and now - _online_cache[0] < ONLINE_CACHE_S:
        return _online_cache[1]
    result = _probe()
    _online_cache = (now, result)
    return result


# ---------------------------------------------------------------- safe_org (prd §11.1)
MAX_ORG_WORDS = 6
MAX_ORG_CHARS = 60
ORG_WORDS = {
    "department", "dept", "agency", "bank", "inc", "llc", "llp", "ltd", "corp", "corporation",
    "company", "co", "office", "service", "services", "police", "court", "bureau", "administration",
    "commission", "authority", "ministry", "treasury", "revenue", "security", "justice", "university",
    "group", "partners", "federal", "national", "state", "county", "city", "government",
    "support", "microsoft", "apple", "google", "amazon", "paypal",
}
PERSON_TITLES = {
    "agent", "officer", "detective", "sergeant", "sgt", "inspector", "mr", "mrs", "ms", "miss",
    "dr", "sir", "madam", "lieutenant", "captain", "special",
}
_BAD_CHARS = re.compile(r"[0-9@,;:/\\|<>{}\[\]#$%*=+?!\"]")
_DOMAIN = re.compile(r"\b[\w-]+\.(?:com|org|net|gov|edu|io|co|us|uk|info|biz|ai|app)\b", re.I)
_WS = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _WS.sub(" ", text).strip().lower()


def _contains_phrase(haystack: str, needle: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(needle) + r"(?!\w)", haystack) is not None


def never_search_from_env() -> list[str]:
    """CALLGUARD_NEVER_SEARCH: comma-separated names (optional; P1 moves this to the UI)."""
    raw = os.environ.get("CALLGUARD_NEVER_SEARCH", "")
    return [n.strip() for n in raw.split(",") if n.strip()]


def org_refusal(org: Any, caller_lines: list[str], never_search: list[str] | None = None) -> str:
    """Why `org` may not be searched, or "" if it may. Reasons never contain the name."""
    if not isinstance(org, str) or not org.strip():
        return "empty"
    name = _WS.sub(" ", org).strip()
    low = name.lower()
    if _BAD_CHARS.search(name) or "http" in low or "www." in low or _DOMAIN.search(name):
        return "digits, links or punctuation"
    words = name.split(" ")
    if len(words) > MAX_ORG_WORDS or len(name) > MAX_ORG_CHARS:
        return "too long"
    if not _contains_phrase(_norm("\n".join(caller_lines)), low):
        return "not said by the caller"
    for blocked in never_search or []:
        b = _norm(blocked)
        if b and (_contains_phrase(low, b) or _contains_phrase(b, low)):
            return "on the never-search list"
    bare = [w.strip(".'-()&").lower() for w in words]
    if any(w in PERSON_TITLES for w in bare):
        return "looks like a person"
    is_org_word = [w in ORG_WORDS or (raw.isupper() and 2 <= len(raw) <= 5)
                   for w, raw in zip(bare, (x.strip(".'-()&") for x in words))]
    if 2 <= len(words) <= 3 and all(w[:1].isupper() for w in words) and not any(is_org_word):
        return "looks like a person"
    return ""


def safe_org(org: Any, caller_lines: list[str], never_search: list[str] | None = None) -> bool:
    return org_refusal(org, caller_lines, never_search) == ""


# ---------------------------------------------------------------- search
def _query_ok(org: Any) -> bool:
    return (
        isinstance(org, str)
        and 0 < len(org.strip()) <= MAX_QUERY_CHARS
        and "\n" not in org
        and "\r" not in org
    )


def search(org: str) -> tuple[Verify, dict | None]:
    """Look up `org` (the exact query). Returns (verify, raw provider JSON or None).

    Never raises. Status: ok | offline | error | not_found. Input that is too
    long or multi-line is refused before anything is sent.
    """
    if not _query_ok(org):
        record_refused()
        return {"org": org if isinstance(org, str) else "", "status": "error"}, None
    query = org.strip()

    if not online():
        entry = _new_entry(TAVILY_HOST, query, "offline")
        _publish(entry)
        return {"org": query, "status": "offline"}, None

    key = os.environ.get("TAVILY_API_KEY", "")
    if not key:
        log.warning("search skipped: TAVILY_API_KEY not set")
        entry = _new_entry(TAVILY_HOST, "", "error")
        _publish(entry)
        return {"org": query, "status": "error"}, None

    # Recorded BEFORE the request leaves; provisional status until we know.
    entry = _new_entry(TAVILY_HOST, query, "error")
    started = time.monotonic()
    raw: dict | None = None
    try:
        with httpx.Client(transport=_transport, timeout=SEARCH_TIMEOUT_S) as client:
            r = client.post(TAVILY_URL, json={"query": query, "max_results": 5},
                            headers={"Authorization": f"Bearer {key}"})
        r.raise_for_status()
        raw = r.json()
        entry["status"] = "ok"
    except (httpx.ConnectError, httpx.ConnectTimeout):
        entry["status"] = "offline"
    except Exception as e:  # never raise to the pipeline
        log.warning("search failed: %s", type(e).__name__)
        entry["status"] = "error"
    log.info("search %s in %.2fs", entry["status"], time.monotonic() - started)
    _publish(entry)

    status = entry["status"]
    if status == "ok" and not (raw or {}).get("results"):
        status = "not_found"
    return {"org": query, "status": status}, raw  # type: ignore[typeddict-item]


# ---------------------------------------------------------------- local model
def local_ollama_post(url: str, payload: dict, timeout: float = 8.0) -> dict:
    """POST JSON to Ollama on localhost and return the JSON reply.

    Raises ValueError for any non-localhost URL, LocalModelError on failure.
    """
    parts = urlsplit(url)
    if parts.scheme != "http" or parts.hostname not in LOCAL_HOSTS:
        raise ValueError("local_ollama_post only talks to http://localhost")
    try:
        with httpx.Client(transport=_transport, timeout=timeout) as client:
            r = client.post(url, json=payload)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        raise LocalModelError(type(e).__name__) from None
