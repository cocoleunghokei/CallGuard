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
- [x] `__main__.py` / `app.py`: FastAPI, static `ui/`, `/ws`
- [x] `pipeline.py`: keep the rolling 30 s transcript in memory, run `check()` every new chunk (skip if one is still running), push `transcript` and `check` messages
- [x] `egress.py`: **the only file that makes network calls.** Every call adds an `EgressEntry` and pushes an `egress` message. Detect offline and return `status: "offline"`
- [x] `--fake` flag: use `audio.fake_stream()` so the UI and demo work without a call
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
- [Sat 16:48] Done: SRV-1 `app.py` (FastAPI, serves `ui/` or a placeholder page if `ui/index.html` is missing, `/ws` with `Hub` broadcast + client dispatch by type, on-connect hooks, thread-safe broadcast) and `__main__.py` (`--browser`, `--host`, `--port`); 8 tests in `tests/server/test_app.py`, `python -m callguard.server --browser` serves 200 + WS | Next: SRV-3 egress.py | Needs (Coco): `fastapi==0.162.2`, `uvicorn[standard]==0.54.0` (websockets for /ws), `httpx==0.28.1`, `python-dotenv==1.2.3`, `pytest==9.2.0` in requirements.txt; bare `pytest` at repo root currently errors collecting `hack1984/continuity-audio-test/test_capture.py` (needs `sounddevice`), suggest a root `pytest.ini` with `testpaths = tests`
- [Sat 17:05] Done: SRV-3 `egress.py` (only httpx/socket importer; `search(org)` Tavily stub: entry recorded before the request, final status pushed as `egress`, offline/error/not_found never raise, refuses >80 chars/newlines with `refused`; `online()` TCP-connect probe cached 15 s, sends no bytes so it is not an egress entry, `CALLGUARD_OFFLINE=1` forces offline; `local_ollama_post(url, payload, timeout=8)` http://localhost only, raises `ValueError` otherwise and `egress.LocalModelError` on failure, not logged). App pushes every entry to the UI and replays the log on connect. 25 tests green | Next: SRV-4 `--fake` + SRV-2 pipeline | Needs: Coco to tell Detection (DET-2) to call `callguard.server.egress.local_ollama_post` and catch `LocalModelError`; confirm the online probe (TCP connect, no payload, not logged) is OK under guardrail 2
- [Sat 17:00] Done: SRV-4 + SRV-2. `pipeline.py`: in-memory rolling 30 s window, check() per caller chunk in one worker thread, skip-if-busy + exactly one rerun on the newest window, pushes `transcript` + `check`, logs latency/window size/risk only (never text), check() errors swallowed. `--fake SCRIPT --fake-speed N` replays once the first UI connects. `.env` at repo root is loaded on start (`TAVILY_API_KEY`, …). Uses real `callguard.audio.fake_stream` / `callguard.detection.check` + `rules.load_rules` when merged, else `server/fakes.py` (phrase-match `fake_check`, source `fallback`). `--fake tests/server/fixtures/s1_government.txt` gives low → watch → danger → danger. 33 tests green | Next: SRV-12 privacy tests | Needs: Detection (via Coco): confirm `check(window, rules)` takes `window` as one string of `caller: …` / `you: …` lines, oldest first (same as the script format); if you want a list of lines instead, say so
