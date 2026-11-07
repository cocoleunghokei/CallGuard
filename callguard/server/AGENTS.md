# Lane: Server (pipeline, WebSocket, search, egress log)

Read the root [AGENTS.md](../../AGENTS.md) first. You own `callguard/server/` and `tests/server/` only.

## Delivers
`python -m callguard.server`, which serves `ui/` at `http://localhost:8000` and the WebSocket at `/ws` (messages in root AGENTS.md section 3), and runs:
```
audio.stream_chunks() → rolling 30 s transcript → detection.check() → WebSocket
                                                └─ claimed_identity → egress.search() → verify message
```

## Tasks
Full list with IDs and "done when": [prd.md §13.4](../../hack1984/prd.md#134-server--callguardserver-testsserver).

**P0**
- [ ] `__main__.py` / `app.py`: FastAPI, static `ui/`, `/ws`
- [ ] `pipeline.py`: keep the rolling 30 s transcript in memory, run `check()` every new chunk (skip if one is still running), push `transcript` and `check` messages
- [ ] `egress.py`: **the only file that makes network calls.** Every call adds an `EgressEntry` and pushes an `egress` message. Detect offline and return `status: "offline"`
- [ ] `--fake` flag: use `audio.fake_stream()` so the UI and demo work without a call
- [ ] Clear the transcript when the call ends or the app stops
- [ ] Surge (SRV-8): `egress.search(org)` with Tavily or Exa (keys from `.env`), send **only** the org name, return the public phone number and source URL. Look each org up once per call
- [ ] `egress.safe_org(org, caller_lines, never_search)` before every search ([prd.md §11.1](../../hack1984/prd.md#111-searching-without-exposing-the-user-or-the-firm)): no digits, emails or links; ≤ 6 words; said by the caller; not a person's name; not on `CALLGUARD_NEVER_SEARCH`. On failure send nothing and log `refused`
- [ ] Safe-path pause state (SRV-9, `gate.py`): never hooks the keyboard

**P1**
- [ ] Scam-report search (SRV-15): second query `"{org}" impersonation scam`, its own egress entry, adds `report` to `verify`
- [ ] Rules editing (SRV-14): `save_rules` / `reset_rules`, refused during a call; custom file in `~/Library/Application Support/Callguard/`
- [ ] Handle `colleague` (a local macOS notification is fine for the demo) and `mark_safe`

## Rules for this lane
- Localhost Ollama traffic doesn't go through `egress.py`, but nothing else may skip it
- Never send transcript text to search, only a `claimed_identity` that passed `safe_org()`
- No keyboard or mouse hooks, event taps or Accessibility permission (the hard gate is cut)

## Status
- (none yet)
