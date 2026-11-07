"""DET-4: load the firm rules and work out which ones a call breaks (prd §8, check C6).

A rule is broken when, from the CALLER's speech:
  * one of its `tactics` was detected, or one of its `keywords` appears, AND
  * every tactic in its optional `requires` list was also detected.
Disabled rules (`enabled: false`) never match. Rules are firm policy, not call
content, so nothing here touches the network or writes to disk.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from callguard.shared.contracts import TACTICS, Rule

DEFAULT_RULES_PATH = Path(__file__).with_name("rules.json")


def load_rules(path: str | Path | None = None) -> list[Rule]:
    """Load rules from `path` (default: the shipped rules.json).

    Entries missing an id, text or tactics list are skipped; unknown tactics
    are dropped. A missing or unreadable file raises: the shipped file is
    covered by tests, and the P1 custom-file fallback (DET-13) handles the rest.
    """
    raw = json.loads(Path(path or DEFAULT_RULES_PATH).read_text(encoding="utf-8"))
    rules: list[Rule] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        rid, text, tactics = item.get("id"), item.get("text"), item.get("tactics")
        if not (isinstance(rid, str) and rid and isinstance(text, str) and isinstance(tactics, list)):
            continue
        rule: Rule = {"id": rid, "text": text, "tactics": [t for t in tactics if t in TACTICS]}
        if isinstance(item.get("keywords"), list):
            rule["keywords"] = [k for k in item["keywords"] if isinstance(k, str) and k.strip()]
        if isinstance(item.get("requires"), list):
            rule["requires"] = [t for t in item["requires"] if t in TACTICS]
        if "enabled" in item:
            rule["enabled"] = item["enabled"] is not False
        rules.append(rule)
    return rules


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
