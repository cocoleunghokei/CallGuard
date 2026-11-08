"""DET-4: load the firm rules and work out which ones a call breaks (prd §8, check C6).

A rule is broken when, from the CALLER's speech:
  * one of its `tactics` was detected, or one of its `keywords` appears, AND
  * every tactic in its optional `requires` list was also detected.
Disabled rules (`enabled: false`) never match. Rules are firm policy, not call
content, so nothing here touches the network or writes to disk.

DET-13 (prd §8.1): a firm can save its own rules to `custom_rules_path()`.
`load_rules_with_source()` prefers that file and falls back to the shipped
defaults if it is missing or invalid. A custom rule may be cues only (keywords,
no tactic): the firm's own phrases, e.g. "gift card".
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

from callguard.shared.contracts import TACTICS, Rule

DEFAULT_RULES_PATH = Path(__file__).with_name("rules.json")
MAX_RULES = 30
MAX_TEXT = 200
MAX_KEYWORDS = 10
MAX_KEYWORD = 40
MIN_KEYWORD = 3  # a 1-2 letter cue would match almost every call


def custom_rules_path() -> Path:
    """Where the firm's own rules live (never inside the repo)."""
    env = os.environ.get("CALLGUARD_RULES_FILE", "").strip()
    if env:
        return Path(env).expanduser()
    return Path.home() / "Library" / "Application Support" / "Callguard" / "rules.json"


def load_rules(path: str | Path | None = None) -> list[Rule]:
    """Load rules from `path` (default: the shipped rules.json).

    Entries missing an id or text, or with neither a known tactic nor a cue
    phrase, are skipped; unknown tactics are dropped. A missing or unreadable file raises: the shipped file is
    covered by tests, and the P1 custom-file fallback (DET-13) handles the rest.
    """
    raw = json.loads(Path(path or DEFAULT_RULES_PATH).read_text(encoding="utf-8"))
    rules: list[Rule] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        rid, text, tactics = item.get("id"), item.get("text"), item.get("tactics", [])
        if not (isinstance(rid, str) and rid and isinstance(text, str) and isinstance(tactics, list)):
            continue
        rule: Rule = {"id": rid, "text": text, "tactics": [t for t in tactics if t in TACTICS]}
        if isinstance(item.get("keywords"), list):
            rule["keywords"] = [k for k in item["keywords"] if isinstance(k, str) and k.strip()]
        if not rule["tactics"] and not rule.get("keywords"):
            continue  # nothing could ever break it
        if isinstance(item.get("requires"), list):
            rule["requires"] = [t for t in item["requires"] if t in TACTICS]
        if "enabled" in item:
            rule["enabled"] = item["enabled"] is not False
        rules.append(rule)
    return rules


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:40] or "rule"


def prepare_rules(raw: Any) -> Any:
    """Give new rules (no id) an id `custom_<slug of text>`, unique in the list.

    Anything that isn't a list of dicts is returned unchanged for
    `validate_rules` to reject with a reason.
    """
    if not isinstance(raw, list) or not all(isinstance(r, dict) for r in raw):
        return raw
    taken = {r["id"] for r in raw if isinstance(r.get("id"), str) and r["id"].strip()}
    out = []
    for r in raw:
        r = dict(r)
        if not (isinstance(r.get("id"), str) and r["id"].strip()):
            base = "custom_" + _slug(r.get("text") if isinstance(r.get("text"), str) else "")
            rid, n = base, 2
            while rid in taken:
                rid, n = f"{base}_{n}", n + 1
            taken.add(rid)
            r["id"] = rid
        out.append(r)
    return out


def validate_rules(raw: Any) -> list[str]:
    """Plain-words errors for a rules list; empty when it is valid (prd §8.1)."""
    if not isinstance(raw, list):
        return ["Rules must be a list."]
    errors: list[str] = []
    if len(raw) > MAX_RULES:
        errors.append(f"At most {MAX_RULES} rules.")
    seen: set[str] = set()
    for i, r in enumerate(raw, 1):
        if not isinstance(r, dict):
            errors.append(f"Rule {i}: not a rule.")
            continue
        rid, text = r.get("id"), r.get("text")
        if not (isinstance(rid, str) and rid.strip()):
            errors.append(f"Rule {i}: missing id.")
        elif rid in seen:
            errors.append(f"Rule {i}: duplicate id {rid}.")
        else:
            seen.add(rid)
        if not (isinstance(text, str) and 1 <= len(text.strip()) <= MAX_TEXT):
            errors.append(f"Rule {i}: the rule text must be 1 to {MAX_TEXT} characters.")
        tactics, keywords, requires = r.get("tactics", []), r.get("keywords", []), r.get("requires", [])
        for name, value in (("tactics", tactics), ("keywords", keywords), ("requires", requires)):
            if not isinstance(value, list):
                errors.append(f"Rule {i}: {name} must be a list.")
        if not all(isinstance(x, list) for x in (tactics, keywords, requires)):
            continue
        bad = [t for t in [*tactics, *requires] if t not in TACTICS]
        if bad:
            errors.append(f"Rule {i}: unknown tactic {bad[0]!r}.")
        if len(keywords) > MAX_KEYWORDS:
            errors.append(f"Rule {i}: at most {MAX_KEYWORDS} phrases.")
        for k in keywords:
            if not (isinstance(k, str) and MIN_KEYWORD <= len(k.strip()) <= MAX_KEYWORD and "\n" not in k):
                errors.append(f"Rule {i}: each phrase must be {MIN_KEYWORD} to {MAX_KEYWORD} characters on one line.")
                break
        if not tactics and not [k for k in keywords if isinstance(k, str) and k.strip()]:
            errors.append(f"Rule {i}: add at least one phrase to listen for.")
        if "enabled" in r and not isinstance(r["enabled"], bool):
            errors.append(f"Rule {i}: on/off must be true or false.")
    return errors


def load_rules_with_source(custom: str | Path | None = None) -> tuple[list[Rule], str]:
    """(rules, "custom") from the firm's file if it exists and is valid, else (defaults, "default")."""
    path = Path(custom) if custom is not None else custom_rules_path()
    try:
        if path.is_file():
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not validate_rules(raw):
                return load_rules(path), "custom"
    except (OSError, ValueError):
        pass
    return load_rules(), "default"


def _norm(text: str) -> str:
    text = text.lower().replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", text)


def match_rules(tactics: Iterable[str], rules: list[Rule], caller_text: str = "") -> list[str]:
    """Return the ids of broken rules, in rules-file order.

    `tactics` must already be caller-only (guard G4): pass the tactics from
    evidence the caller said. `caller_text` is the caller's lines from the
    window, used for keyword matching; never pass the user's own lines.
    """
    found = set(tactics)
    text = _norm(caller_text)
    broken: list[str] = []
    for rule in rules:
        if rule.get("enabled", True) is False:
            continue
        if not set(rule.get("requires", [])) <= found:
            continue
        by_tactic = bool(found & set(rule.get("tactics", [])))
        by_keyword = bool(text) and any(_norm(k) in text for k in rule.get("keywords", []))
        if (by_tactic or by_keyword) and rule["id"] not in broken:
            broken.append(rule["id"])
    return broken
