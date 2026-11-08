"""SRV-8 live check: python -m callguard.server.livecheck [ORG ...]

Runs the real Tavily lookup (Exa fallback) for 5 well-known org names and
prints, per org: status, phone, source URL and every egress entry it made.
Needs TAVILY_API_KEY (from .env at the repo root or the environment).

Each org name is passed as its own caller line, so safe_org() sees it as
"said by the caller", exactly as in a real call. Only the org name is sent.
Exit code 0 when every org came back `ok` with a phone, else 1.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from callguard.server import egress

ORGS = [
    "Department of Justice",
    "Internal Revenue Service",
    "Social Security Administration",
    "Federal Bureau of Investigation",
    "Chase Bank",
]
REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(REPO_ROOT / ".env")


def run(orgs: list[str], out=print) -> int:
    if not os.environ.get("TAVILY_API_KEY", "").strip():
        out("TAVILY_API_KEY is not set (.env or environment): nothing sent.")
        return 2
    sent: list[dict] = []
    egress.subscribe(sent.append)
    ok = 0
    for org in orgs:
        before = len(sent)
        v = egress.search(org, [org])
        if v.get("status") == "ok" and v.get("phone"):
            ok += 1
        out(f"{org}: {v.get('status')}  phone={v.get('phone', '-')}  source={v.get('source_url', '-')}")
        for e in sent[before:]:
            out(f"    egress {e['destination']} sent={e['sent']!r} status={e['status']}")
    out(f"{ok}/{len(orgs)} returned a phone number")
    return 0 if ok == len(orgs) else 1


if __name__ == "__main__":
    _load_env()
    sys.exit(run(sys.argv[1:] or ORGS))
