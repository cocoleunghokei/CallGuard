# AGENTS.md: Callguard (HACK1984)

Every coding agent and every teammate reads this file first, then the `AGENTS.md` in the lane they work in.
Why we're building this: [hack1984/background.md](hack1984/background.md). What and when: [hack1984/project-plan.md](hack1984/project-plan.md).

**Callguard** is a Mac desktop app. It listens to work calls, transcribes them on the laptop, detects scam scripts, checks them against the firm's own rules, and warns the user. **Everything runs locally.**

Code freeze: **Sun Nov 8, 11:00 ET**. After that, only the Lead merges.

---

## 1. Lanes

Each lane owns one folder. Work only in your own lane.

| Lane | Folder | Owner (plan role) | Branch | Delivers |
|---|---|---|---|---|
| Audio | `callguard/audio/` | Audio + transcription | `lane/audio` | Call audio in, `TranscriptChunk`s out |
| Detection | `callguard/detection/` | Model + backend (Lead owns the prompt and rules text) | `lane/detection` | Transcript in, `ScamCheck` out |
| Server | `callguard/server/` | Model + backend | `lane/server` | Pipeline, WebSocket, search lookup, egress log |
| UI | `ui/` | Screen + demo | `lane/ui` | Risk meter, warnings, "what left this device" log |
| Lead | `hack1984/`, `AGENTS.md`, `callguard/shared/` | Lead / product (Coco) | `lane/lead` | Plan, demo script, test scripts, contracts |

Each lane folder has its own `AGENTS.md` with its tasks, its rules and a **Status** section.

## 2. Guardrails (apply to every lane)

**Privacy (this is the product, so breaking a rule here is a bug)**
1. No audio or transcript is ever written to disk, logged, or sent over the network. Debug output may print only the last 80 characters of a transcript.
2. All network calls go through `callguard/server/egress.py`. Every call records an entry in the egress log. No other file may import `requests`, `httpx`, `urllib` or a search SDK.
3. The only thing allowed to leave the device is the **claimed organization name**, sent to Tavily or Exa.
4. With the Wi-Fi off, everything works except search, which shows "offline, skipped".
5. The model runs on Ollama at `localhost`. Never call a cloud LLM from app code.

**Collaboration**
6. Edit only your own lane's folder. If you need something from another lane, add it to that lane's **Requests** list in its `AGENTS.md` and to your own Status.
7. The contracts in `callguard/shared/contracts.py` and section 3 below are the only shared interfaces. To change them, the Lead edits both, then posts a note in every lane's Status. Adding a new optional field is fine; never rename or remove one.
8. Until another lane is ready, build against fakes of its contract (a fake transcript stream, a fixed `ScamCheck`). Never block on another lane.
9. Small commits and merges: pull with `git pull --rebase origin main`, then merge into `main` at least every 2 hours. Never force-push `main`.
10. Never commit API keys. Keys go in `.env` (ignored by git): `TAVILY_API_KEY`, `EXA_API_KEY`.

**Code**
11. Python 3.11+. Dependencies go in `requirements.txt` (append only, one per line, pinned with `==`).
12. Tests go in `tests/<lane>/`, and the whole suite runs with `pytest`. Tests must pass without network, without Ollama and without audio devices, so use fakes.
13. Keep it simple. This is a 24-hour demo: no extra frameworks, no abstraction layers we don't need yet.

## 3. Contracts

The code version is `callguard/shared/contracts.py`; this section is the readable version.

**`TranscriptChunk`** (Audio → Server), one every ~3 s:
```json
{"speaker": "caller | you", "text": "…", "start": 12.0, "end": 15.0, "language": "en | zh"}
```

**`Rule`** (loaded from `callguard/detection/rules.json`):
```json
{"id": "no_bank_changes_by_phone", "text": "We never change vendor bank details by phone.", "tactics": ["bank_change"]}
```

**`ScamCheck`** (Detection → Server → UI), the model's output:
```json
{
  "risk": "low | watch | danger",
  "tactics": ["authority", "secrecy", "urgency", "threat", "credential_request", "bank_change", "bypass_approval"],
  "claimed_identity": "Department of Justice | null",
  "rules_broken": ["no_bank_changes_by_phone"],
  "reason": "Caller claims to be a government official and asked you not to tell colleagues.",
  "next_step": "Hang up and call the agency's public number."
}
```

**`EgressEntry`** (Server → UI), one for every network call:
```json
{"time": "2026-11-07T19:02:11", "destination": "api.tavily.com", "sent": "Department of Justice", "status": "ok | offline | error"}
```

**WebSocket** `ws://localhost:8000/ws`. Every message from the Server to the UI is `{"type": …, "data": …}`:

| `type` | `data` |
|---|---|
| `transcript` | `TranscriptChunk` |
| `check` | `ScamCheck` |
| `verify` | `{"org": "…", "phone": "…", "source_url": "…"}`, or `{"org": "…", "status": "offline"}` |
| `egress` | `EgressEntry` |
| `status` | `{"listening": true, "online": false}` |

UI → Server: `{"type": "colleague"}` for "Check with a colleague", and `{"type": "mark_safe"}`.

## 4. Commands

```bash
pip install -r requirements.txt     # once
ollama pull qwen2.5:7b              # once (fallback: qwen2.5:3b)
python -m callguard.server          # runs the app, then open http://localhost:8000
pytest                              # all tests, offline
```
Whoever first makes one of these work, or changes one, updates this section.

## 5. How to report status

At the end of every work block, and whenever you're blocked, update the **Status** section in **your own lane's** `AGENTS.md` (never another lane's):
```
- [Sat 16:40] Done: … | Next: … | Blocked on: … (lane)
```
Before starting work, read the Status of every lane you depend on.

## 6. Checkpoints (from the plan)

- Sat 13:30: Continuity test done, Zoom route works (Audio)
- Sat 19:00: first full run, call to screen (all)
- Sat 22:00: P0 complete, Wi-Fi-off run works. Decide whether to start P1 or keep fixing P0
- Sun 02:00: P1 in or cut
- Sun 09:00: backup video recorded (UI)
- Sun 11:00: code freeze
