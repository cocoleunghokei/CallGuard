# AGENTS.md: Callguard (HACK1984)

Every coding agent reads this file first, then the `AGENTS.md` of its lane.
**Team:** Coco is the only human and acts as Lead. Every other lane is run by a coding agent in its own git worktree. Agents never merge into `main`; Coco reviews and merges.
Why we're building this: [hack1984/background.md](hack1984/background.md). What and when: [hack1984/project-plan.md](hack1984/project-plan.md). Detailed requirements by lane (IDs like `DET-6`): [hack1984/prd.md](hack1984/prd.md).

**Callguard** is a Mac desktop app. It listens to work calls, transcribes them on the laptop, detects scam scripts, checks them against the firm's own rules, and warns the user. **Everything runs locally.**

Code freeze: **Sun Nov 8, 11:00 ET**.

---

## 1. Lanes

Each lane owns one folder. Work only in your own lane.

| Lane | Folder | Run by | Branch | Delivers |
|---|---|---|---|---|
| Audio | `callguard/audio/` | Agent + Coco (hardware tests need hands on the Mac) | `lane/audio` | Call audio in, `TranscriptChunk`s out |
| Detection | `callguard/detection/` | Agent (Coco signs off on the prompt and rules text) | `lane/detection` | Transcript in, `ScamCheck` out |
| Server | `callguard/server/` | Agent | `lane/server` | Pipeline, WebSocket, search lookup, egress log |
| UI | `ui/` | Agent | `lane/ui` | Risk meter, warnings, "what left this device" log |
| Lead | `hack1984/`, `AGENTS.md`, `callguard/shared/`, `requirements.txt` | Coco | `main` | Plan, demo script, test scripts, contracts |

Each lane folder has its own `AGENTS.md` with its tasks, its rules and a **Status** section.

## 2. Guardrails (apply to every lane)

**Privacy (this is the product, so breaking a rule here is a bug)**
1. No audio or transcript is ever written to disk, logged, or sent over the network. Debug output may print only the last 80 characters of a transcript.
2. All network calls go through `callguard/server/egress.py`. Every call records an entry in the egress log. No other file may import `requests`, `httpx`, `urllib` or a search SDK.
3. The only thing allowed to leave the device is the **claimed organization name**, sent to Tavily or Exa, either alone or inside a fixed search template (e.g. `"{org}" impersonation scam`). The egress log shows the exact query.
4. With the Wi-Fi off, everything works except search, which shows "offline, skipped".
5. The model runs on Ollama at `localhost`. Never call a cloud LLM from app code.

**Collaboration**
6. Edit only your own lane's folder (and `tests/<lane>/`). If you need something from another lane, write it under **Needs** in your own Status. Coco passes it on. Never edit another lane's files, including its `AGENTS.md`.
7. The contracts in `callguard/shared/contracts.py` and section 3 below are the only shared interfaces. Agents never edit them: write the change you need under **Needs**, and Coco updates both. Adding a new optional field is fine; never rename or remove one.
8. Until another lane is ready, build against fakes of its contract (a fake transcript stream, a fixed `ScamCheck`). Never block on another lane.
9. Commit small and often on your lane branch. Before starting a task, run `git rebase main` to pick up the other lanes' merged work. Never commit to, merge into or push `main`; Coco does that.
10. Never commit API keys. Keys go in `.env` (ignored by git): `TAVILY_API_KEY`, `EXA_API_KEY`.

**Code**
11. Python 3.11+. To add a dependency, put it under **Needs** with its pinned version (`pkg==x.y`); Coco adds it to `requirements.txt`.
12. Tests go in `tests/<lane>/`, and the whole suite runs with `pytest`. Tests must pass without network, without Ollama and without audio devices, so use fakes.
13. Keep it simple. This is a 24-hour demo: no extra frameworks, no abstraction layers we don't need yet.

## 3. Contracts

The code version is `callguard/shared/contracts.py`; this section is the readable version (v2, from [prd.md §12](hack1984/prd.md#12-contract-changes-v2)). Fields marked *optional* may be missing; code must cope.

**`TranscriptChunk`** (Audio → Server), one every ~3 s:
```json
{"speaker": "caller | you", "text": "…", "start": 12.0, "end": 15.0, "language": "en | zh"}
```

**`Rule`** (loaded from `callguard/detection/rules.json`, or the firm's custom file, see prd.md §8.1):
```json
{"id": "no_bank_changes_by_phone", "text": "We never change vendor bank details by phone.", "tactics": ["bank_change"],
 "keywords": ["new account"], "requires": ["authority"], "enabled": true}
```
`keywords`, `requires` and `enabled` (default `true`) are optional.

**`ScamCheck`** (Detection → Server → UI), the model's output:
```json
{
  "risk": "low | watch | danger",
  "tactics": ["authority", "secrecy", "urgency", "threat", "credential_request", "bank_change", "bypass_approval",
              "payment_request", "remote_access", "personal_data_request", "inside_knowledge"],
  "claimed_identity": "Department of Justice | null",
  "rules_broken": ["no_bank_changes_by_phone"],
  "reason": "Caller claims to be a government official and asked you not to tell colleagues.",
  "next_step": "Hang up and call the agency's public number.",
  "confidence": 0.99,
  "evidence": [{"tactic": "secrecy", "quote": "do not tell your colleagues", "strength": "clear | hint | phrase", "speaker": "caller"}],
  "safe_signals": ["callback_known_number | follows_normal_approval | no_money_or_data_asked | asks_in_writing"],
  "source": "model | fast | fallback"
}
```
`confidence`, `evidence`, `safe_signals` and `source` are optional. `evidence.quote` is at most 80 characters, copied verbatim.

**`EgressEntry`** (Server → UI), one for every network call, including refused ones:
```json
{"time": "2026-11-07T19:02:11", "destination": "api.tavily.com", "sent": "\"Department of Justice\" impersonation scam", "status": "ok | offline | error | refused"}
```
`sent` is the exact query. `refused` means the name failed `egress.safe_org()` (prd.md §11.1): nothing was sent and `sent` is `""`.

**WebSocket** `ws://localhost:8000/ws`. Every message from the Server to the UI is `{"type": …, "data": …}`:

| `type` | `data` |
|---|---|
| `transcript` | `TranscriptChunk` |
| `check` | `ScamCheck` |
| `verify` | `{"org": "…", "phone": "…", "source_url": "…", "status": "ok | offline | not_found | error", "report": {"summary": "…", "source_url": "…", "date": "2026-10"}}`. Only `org` is required; `report` (P1) is omitted when nothing recent is found |
| `egress` | `EgressEntry` |
| `status` | `{"listening": true, "online": false, "model": "ok | degraded | offline", "gate": "off | on", "audio_ok": true, "audio_message": "…"}` (`model`, `gate`, `audio_ok`, `audio_message` optional; the audio fields come only in live mode) |
| `gate` | `{"state": "off | armed | locked", "reason": "…", "release_in": 120}`. The safe-path pause; it never blocks typing |
| `call` | `{"state": "started | ended"}` |
| `rules` | `[Rule]`, sent on connect and after every save or reset. The message also has optional top-level `"source": "default | custom"`, `"never_search": ["…"]` (app-edited names, P1) and `"never_search_env": 2` (count from `.env`, P1) |
| `rules_saved` | `{"ok": true}` or `{"ok": false, "errors": ["…"]}` (P1) |
| `contacts` | `[{"id": "oit | manager", "role": "IT security (OIT)", "name": "…", "phone": "…"}]`, sent on connect and after every save (also a refused one, so the UI shows what is really saved). Empty strings when not set. Stored only in `~/Library/Application Support/Callguard/contacts.json` |
| `contacts_saved` | `{"ok": true}` or `{"ok": false, "errors": ["…"]}` |

UI → Server:

| `type` | Extra fields | Meaning |
|---|---|---|
| `colleague` | | "Check with a colleague" |
| `mark_safe` | | "Mark as safe" |
| `gate_release` | `"how": "hang_up | colleague | mark_safe"` | User chose a way out of the pause |
| `end_call` | | User ended the call in Callguard |
| `save_rules` | `"data": [Rule]`, optional `"never_search": ["…"]` | P1: save the firm's custom rules and never-search list (refused during a call) |
| `reset_rules` | | P1: delete the custom rules, back to defaults (keeps the never-search list) |
| `save_contacts` | `"data": [Contact]` | Save the emergency contacts' name and phone (allowed during a call; roles are fixed) |

## 4. Commands

```bash
pip install -r requirements.txt     # once
ollama pull qwen2.5:7b              # once (fallback: qwen2.5:3b, set CALLGUARD_MODEL)
python -m callguard.server          # the app in its own Mac window, listening live (mic + BlackHole)
python -m callguard.server --fake tests/detection/scripts/s1_government.txt  # replay a script instead of live audio
python -m callguard.server --no-audio  # window only, no mic (try the UI)
python -m callguard.server --browser   # dev only: serve http://localhost:8000 for the browser (combine with the above)
python -m callguard.audio.health    # are the mic and BlackHole inputs ready?
pytest                              # all tests, offline (browser tests skip without playwright)
```
Judge demo link: https://cocoleunghokei.github.io/scam-call-detector/ (`pages/index.html` + the replay of `ui/` from `main`, deployed by `.github/workflows/pages.yml` on every push to `main` that touches `ui/` or `pages/`; one-time setup: Settings → Pages → Source: GitHub Actions).
Live audio needs `CALLGUARD_WHISPER_DIR` (local faster-whisper small model) in `.env`; optional `CALLGUARD_CALLER_DEVICE` (default "BlackHole 2ch"), `CALLGUARD_MIC_DEVICE`, `CALLGUARD_CALL_IDLE_S` (a live call ends after this much silence, default 45). Full demo-machine steps: [ui/DEMO.md](ui/DEMO.md).
Whoever first makes one of these work, or changes one, updates this section.

## 5. How to report status

After every task, and whenever you're blocked, add a line to the **Status** section of **your own lane's** `AGENTS.md`, then commit:
```
- [Sat 16:40] Done: … | Next: … | Needs: … (from which lane, or from Coco)
```
Then stop and tell Coco what's ready to review. Before starting work, read the Status of every lane you depend on (on `main`).

## 6. Checkpoints (from the plan)

- Sat 13:30: Continuity test done, Zoom route works (Audio)
- Sat 19:00: first full run, call to screen (all)
- Sat 22:00: P0 complete, Wi-Fi-off run works. Decide whether to start P1 or keep fixing P0
- Sun 02:00: P1 in or cut
- Sun 09:00: backup video recorded (UI)
- Sun 11:00: code freeze
