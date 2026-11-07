# Lane: Server (pipeline, WebSocket, search, egress log)

Read the root [AGENTS.md](../../AGENTS.md) first. You own `callguard/server/` and `tests/server/` only.

## Delivers
`python -m callguard.server`, which serves `ui/` at `http://localhost:8000` and the WebSocket at `/ws` (messages in root AGENTS.md section 3), and runs:
```
audio.stream_chunks() → rolling 30 s transcript → detection.check() → WebSocket
                                                └─ claimed_identity → egress.search() → verify message
```

## Tasks
**P0**
- [ ] `__main__.py` / `app.py`: FastAPI, static `ui/`, `/ws`
- [ ] `pipeline.py`: keep the rolling 30 s transcript in memory, run `check()` every new chunk (skip if one is still running), push `transcript` and `check` messages
- [ ] `egress.py`: **the only file that makes network calls.** Every call adds an `EgressEntry` and pushes an `egress` message. Detect offline and return `status: "offline"`
- [ ] `--fake` flag: use `audio.fake_stream()` so the UI and demo work without a call
- [ ] Clear the transcript when the call ends or the app stops

**P1**
- [ ] Surge: `egress.search(org)` with Tavily or Exa (keys from `.env`), send **only** the org name, return the public phone number and source URL. Look each org up once per call
- [ ] Handle `colleague` (a local macOS notification is fine for the demo) and `mark_safe`

## Rules for this lane
- Localhost Ollama traffic doesn't go through `egress.py`, but nothing else may skip it
- Never send transcript text to search, only `claimed_identity`

## Requests from other lanes
- (none yet)

## Status
- (none yet)
