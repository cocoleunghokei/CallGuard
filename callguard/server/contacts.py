"""Emergency contacts: who the user calls when a call feels wrong.

The UI's "Emergency contacts" tab shows them; the user can edit name and phone.
They are the user's own colleagues, never call content, and never leave the
device: they are only read from and written to one local file,
``~/Library/Application Support/Callguard/contacts.json`` (or
``$CALLGUARD_DATA_DIR/contacts.json``). Contents are never logged.

Protocol (root AGENTS.md section 3):
  Server -> UI  ``contacts``        [Contact], on connect and after every save (also a refused one)
  Server -> UI  ``contacts_saved``  {"ok": true} | {"ok": false, "errors": [...]}
  UI -> Server  ``save_contacts``   "data": [Contact]
"""
from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from callguard.shared.contracts import Contact

log = logging.getLogger("callguard.server")

# The roles are fixed; only name and phone are edited.
DEFAULTS: list[Contact] = [
    {"id": "oit", "role": "IT security (OIT)", "name": "OIT help desk", "phone": ""},
    {"id": "manager", "role": "Line manager", "name": "", "phone": ""},
]
MAX_NAME = 60
MAX_PHONE = 30
PHONE_OK = re.compile(r"^[0-9+()\-.\s]*(?:(?:ext\.?|x)\s*[0-9]+)?$", re.IGNORECASE)


def path() -> Path:
    base = os.environ.get("CALLGUARD_DATA_DIR")
    root = Path(base) if base else Path.home() / "Library" / "Application Support" / "Callguard"
    return root / "contacts.json"


def _merge(saved: dict[str, dict]) -> list[Contact]:
    out: list[Contact] = []
    for d in DEFAULTS:
        s = saved.get(d["id"], {})
        name, phone = s.get("name"), s.get("phone")
        out.append({
            **d,
            "name": name if isinstance(name, str) else d["name"],
            "phone": phone if isinstance(phone, str) else d["phone"],
        })
    return out


def load() -> list[Contact]:
    """Saved contacts over the defaults. A missing or broken file gives the defaults."""
    try:
        raw = json.loads(path().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _merge({})
    except (OSError, ValueError):
        log.warning("contacts file unreadable, using defaults")
        return _merge({})
    saved = {c["id"]: c for c in raw if isinstance(c, dict) and isinstance(c.get("id"), str)} \
        if isinstance(raw, list) else {}
    return _merge(saved)


def validate(data: Any) -> tuple[list[Contact], list[str]]:
    """Plain-words errors; on success the cleaned list (unknown ids dropped)."""
    if not isinstance(data, list):
        return [], ["Contacts must be a list."]
    known = {d["id"]: d for d in DEFAULTS}
    saved: dict[str, dict] = {}
    errors: list[str] = []
    for c in data:
        if not isinstance(c, dict) or c.get("id") not in known:
            continue
        role = known[c["id"]]["role"]
        name, phone = c.get("name", ""), c.get("phone", "")
        if not isinstance(name, str) or not isinstance(phone, str):
            errors.append(f"{role}: name and phone must be text.")
            continue
        name, phone = " ".join(name.split()), " ".join(phone.split())
        if len(name) > MAX_NAME:
            errors.append(f"{role}: name is longer than {MAX_NAME} characters.")
        if len(phone) > MAX_PHONE:
            errors.append(f"{role}: phone is longer than {MAX_PHONE} characters.")
        elif not PHONE_OK.match(phone):
            errors.append(f"{role}: phone can only have digits, spaces, + ( ) - . and an extension.")
        saved[c["id"]] = {"name": name, "phone": phone}
    if errors:
        return [], errors
    return _merge(saved), []


def save(contacts: list[Contact]) -> None:
    """Atomic write, so a crash never leaves half a file."""
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps([{"id": c["id"], "name": c["name"], "phone": c["phone"]} for c in contacts], indent=2)
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=".contacts-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(body)
        os.replace(tmp, p)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def attach(hub) -> None:
    """Send contacts to every UI on connect; handle ``save_contacts``."""

    async def hello(ws) -> None:
        await hub.send(ws, "contacts", load())

    async def on_save(msg: dict) -> None:
        contacts, errors = validate(msg.get("data"))
        if not errors:
            try:
                save(contacts)
            except OSError:
                errors = ["Couldn't save on this laptop. Your changes last until you close CallGuard."]
        if errors:
            await hub.broadcast("contacts", load())  # the UI goes back to what is really saved
            await hub.broadcast("contacts_saved", {"ok": False, "errors": errors})
            return
        await hub.broadcast("contacts", contacts)
        await hub.broadcast("contacts_saved", {"ok": True})

    hub.on_connect.append(hello)
    hub.handle("save_contacts", on_save)
