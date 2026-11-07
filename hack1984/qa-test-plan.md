# Callguard QA test plan (HACK1984)

Owner: Coco (Lead) · Status: v1 · Last updated: Sat Nov 7, 2026

Read with: [prd.md](prd.md) (requirements and IDs), [eval-suite.md](eval-suite.md) (model quality, DET-9/11), root [AGENTS.md](../AGENTS.md) (guardrails, contracts).

This is the list of test cases every lane implements, plus the end-to-end and manual checks Coco runs on the demo Mac. `eval-suite.md` answers "is the model good?"; this file answers "does every part do what the PRD says, and does nothing leak?"

---

## Contents

1. [How to use this file](#1-how-to-use-this-file)
2. [Shared and guardrail tests (Lead)](#2-shared-and-guardrail-tests-lead)
3. [Audio](#3-audio)
4. [Detection](#4-detection)
5. [Server](#5-server)
6. [UI](#6-ui)
7. [End to end (integration)](#7-end-to-end-integration)
8. [Failure-mode matrix](#8-failure-mode-matrix)
9. [Demo-day QA run](#9-demo-day-qa-run)
10. [Gaps and decisions found while writing this](#10-gaps-and-decisions-found-while-writing-this)
11. [Prompt snippet to hand each agent](#11-prompt-snippet-to-hand-each-agent)

---

## 1. How to use this file

- **IDs.** `QA-<LANE>-NN`. Name the test function after the ID (`test_qa_srv_14_watch_decays_after_three_lows`) so a failing test points straight back here.
- **Layer.** `unit` and `privacy` run in `pytest`, offline, with no Ollama and no audio devices (guardrail 12). `eval` needs Ollama. `manual` needs the demo Mac and Coco. `e2e` needs everything merged.
- **P.** P0 cases must be green before the Sat 22:00 decision. P1 cases come with their P1 feature.
- **"Done when"** for a lane task now includes its QA cases. A lane reports QA progress in its Status line: `QA: 18/22 P0 green`.
- **Shared fixtures.** All lanes use the scenario scripts in `tests/detection/scripts/` (format in prd §15.2). Until Detection ships them, a lane may keep a tiny copy of S1 and B3 in its own `tests/<lane>/fixtures/`.
- **Sentinel string.** Privacy tests put a unique sentinel in a transcript line (e.g. `ZEBRA-SENTINEL-7731 do not tell your colleagues`) and then search stdout, logs, files, egress entries and notifications for it. Finding it anywhere it shouldn't be is a failure.

---

## 2. Shared and guardrail tests (Lead)

Location: `tests/shared/`. These exist now and run against whatever is on `main`.

| ID | P | Layer | Test | Expected |
|---|---|---|---|---|
| QA-SH-01 | P0 | unit | `TACTICS` matches the weights table in prd §6.3 and the tactic list in AGENTS.md §3 | Same 11 names, same order is not required |
| QA-SH-02 | P0 | unit | Every JSON example in AGENTS.md §3 has all required keys of its TypedDict and no unknown keys | Pass for TranscriptChunk, Rule, ScamCheck, EgressEntry |
| QA-SH-03 | P0 | unit | Every `MessageType` and `ClientMessageType` appears in AGENTS.md §3 tables, and the reverse | No drift between code and doc |
| QA-SH-04 | P0 | unit | All v2 fields are `NotRequired` (guardrail 7: v1 code keeps working) | `__required_keys__` unchanged from v1 |
| QA-SH-05 | P0 | privacy | Repo-wide import scan: no file under `callguard/` except `server/egress.py` imports `requests`, `httpx`, `urllib`, `http.client`, `socket`, `aiohttp`, `tavily`, `exa_py` | Backstop for SRV-12a |
| QA-SH-06 | P0 | privacy | No cloud LLM SDK anywhere in `callguard/` or `requirements.txt` (`openai`, `anthropic`, `google.generativeai`, `cohere`, `mistralai`, `groq`) | Guardrail 5 |
| QA-SH-07 | P0 | privacy | No keyboard/mouse hooks anywhere: `pynput`, `keyboard`, `Quartz`, `CGEventTap`, `addGlobalMonitorForEvents` | prd §7.5 "never block" |
| QA-SH-08 | P0 | privacy | No `.env` file and no string that looks like a Tavily/Exa key (`tvly-…`) is tracked by git | Guardrail 10 |
| QA-SH-09 | P0 | privacy | No source file writes audio: no `sf.write`, `soundfile.write`, `wave.open(…, "w")`, `np.save` outside `hack1984/continuity-audio-test/` | Guardrail 1 |

---

## 3. Audio

Location: `tests/audio/`. Fakes: a fake `sounddevice` module that yields numpy blocks, and a fake `WhisperModel` that returns fixed segments.

### 3.1 `fake_stream()` (AUD-5): first, because every other lane needs it

| ID | P | Layer | Test | Expected |
|---|---|---|---|---|
| QA-AUD-01 | P0 | unit | Parse a §15.2 script: `#` lines and blank lines skipped | Only `caller:`/`you:` lines become chunks |
| QA-AUD-02 | P0 | unit | Split on the **first** colon only: `caller: Meet at 5:30, OK?` | text = `Meet at 5:30, OK?` |
| QA-AUD-03 | P0 | unit | Timing: line *i* has `start = 3*i`, `end = start + 3`; strictly increasing | Matches eval-suite §4 step 1 |
| QA-AUD-04 | P0 | unit | Every chunk has exactly the `TranscriptChunk` keys, `speaker ∈ {caller, you}`, `language == "en"`, floats for times | Contract-valid |
| QA-AUD-05 | P0 | unit | `speed=0` yields 20 lines in < 50 ms; `speed=1` calls `time.sleep(3)` per line (patched) | No real sleeping in tests |
| QA-AUD-06 | P0 | unit | Unknown speaker (`boss: hi`) or a line with no colon | `ValueError` naming the file and line number |
| QA-AUD-07 | P0 | unit | Every file in `tests/detection/scripts/*.txt` replays (parametrized; skipped while the folder is empty) | No errors |
| QA-AUD-08 | P1 | unit | Leading/trailing whitespace and Windows line endings (`\r\n`) | Stripped, same chunks |

### 3.2 Capture and transcription (AUD-2, AUD-3, AUD-4)

| ID | P | Layer | Test | Expected |
|---|---|---|---|---|
| QA-AUD-10 | P0 | unit | Capture produces 3 s blocks of 16 kHz mono float32 (48 000 samples) from a fake device at 48 kHz stereo | Shape and dtype correct |
| QA-AUD-11 | P0 | unit | Caller blocks come from the BlackHole device, `you` blocks from the mic; `CALLGUARD_CALLER_DEVICE` / `CALLGUARD_MIC_DEVICE` override names | Labels follow the source (C1) |
| QA-AUD-12 | P0 | unit | Missing device | Plain-language error (`"BlackHole 2ch not found…"`), no traceback to the user |
| QA-AUD-13 | P0 | unit | Silence gate (C2): all-zeros block and a block under the RMS threshold never reach the transcriber; a loud block does | Fake model call count |
| QA-AUD-14 | P0 | unit | Transcriber returns `""` or whitespace | No chunk yielded |
| QA-AUD-15 | P0 | unit | Model is constructed **once** across 50 chunks | Constructor count == 1 |
| QA-AUD-16 | P0 | unit | Model load uses `CALLGUARD_WHISPER_DIR`, sets `HF_HUB_OFFLINE=1` first, passes `language="en"`, `vad_filter=True`, `compute_type="int8"` | Args on the fake |
| QA-AUD-17 | P0 | unit | `stream_chunks()` merges both speakers in time order; `start`/`end` relative to call start (fake clock) | Interleaved, monotonic |
| QA-AUD-18 | P0 | unit | Importing `callguard.audio` works with `sounddevice` and `faster_whisper` missing (`sys.modules[...] = None`) | Lazy imports; pytest passes on Linux CI |

### 3.3 Audio privacy (AUD-6)

| ID | P | Layer | Test | Expected |
|---|---|---|---|---|
| QA-AUD-20 | P0 | privacy | Run capture → transcribe → `stream_chunks()` for 10 fake blocks with `open` (write modes), `os.write`, `soundfile.write`, `wave.open`, `numpy.save` patched | Zero write calls |
| QA-AUD-21 | P0 | privacy | Sentinel line transcribed by the fake model; capture `capsys` and `caplog` | Sentinel never printed; no output line has > 80 chars of transcript |
| QA-AUD-22 | P0 | privacy | After the generator is closed, no reference to audio arrays remains (weakref to the last block is dead after `gc.collect()`) | Audio dropped after transcription |

### 3.4 Audio manual checks (Coco, demo Mac)

| ID | P | Layer | Test | Expected |
|---|---|---|---|---|
| QA-AUD-M1 | P0 | manual | `--rms` for 10 s: teammate talks, then you talk (headphones on) | Caller RMS moves only when they talk; mic only when you do |
| QA-AUD-M2 | P0 | manual | Zoom: teammate reads S1 | Words on screen ≤ 3 s after spoken, labelled `caller` |
| QA-AUD-M3 | P0 | manual | Teams (desktop or web) same as M2 | Same |
| QA-AUD-M4 | P1 | manual | Continuity call (only if AUD-1 passed) | Same |
| QA-AUD-M5 | P0 | manual | Wi-Fi off, cold start: transcription works | Whisper loads from local dir, no download |
| QA-AUD-M6 | P0 | manual | 15-minute call: memory flat (Activity Monitor), timestamps don't drift | No leak |
| QA-AUD-M7 | P1 | manual | Unplug / switch output away from BlackHole mid-call (FaceTime does this) | Warning in panel, no crash (AUD-9) |
| QA-AUD-M8 | P0 | manual | After the run, `find ~ -newer <marker> -name "*.wav" -o -name "*.flac"` | No audio files |

---

## 4. Detection

Location: `tests/detection/`. Fakes: a fake `post` callable returning canned Ollama responses. The eval suite's L1 replay covers whole scripts; these cases cover each function.

### 4.1 `parse.py` (DET-3, C5)

| ID | P | Layer | Test | Expected |
|---|---|---|---|---|
| QA-DET-01 | P0 | unit | Valid model JSON | `ScamCheck` with all required keys, `source: "model"` |
| QA-DET-02 | P0 | unit | Fuzz set of 20 malformed outputs (list below) | Never raises; always a valid `ScamCheck` |
| QA-DET-03 | P0 | unit | Unknown tactics (`"fear"`, `"phishing"`) dropped; `"Authority"` normalised to `authority` | Only `TACTICS` survive |
| QA-DET-04 | P0 | unit | Evidence quote not in the window | Dropped (hallucination guard) |
| QA-DET-05 | P0 | unit | Quote matches the window except case or extra spaces | Kept (match after lowercasing and collapsing whitespace) |
| QA-DET-06 | P0 | unit | Quote longer than 80 chars | Truncated to 80 |
| QA-DET-07 | P0 | unit | Evidence labelled `speaker: "caller"` but the quote appears only in a `you:` line | Dropped (G4 can't be bypassed by the model mislabelling) |
| QA-DET-08 | P0 | unit | `claimed_identity` of `""`, `"null"`, `"None"`, `"unknown"`, `"N/A"` | `None` |
| QA-DET-09 | P0 | unit | `reason` of 60 words; `next_step` of 500 chars | Truncated (reason ≤ 20 words) |
| QA-DET-10 | P0 | unit | Unknown `safe_signals` dropped | Only `SAFE_SIGNALS` survive |

Fuzz set for QA-DET-02: empty string; `null`; `[]`; `"danger"`; truncated JSON; JSON in a ```` ```json ```` fence (should be **extracted**, not failed); JSON followed by prose; `risk: "high"`; `risk: 3`; `tactics: "authority"` (string, not list); `tactics: null`; missing `risk`; missing everything but `risk`; `evidence` as a dict; evidence item missing `quote`; 100 KB string; NUL bytes; emoji and CJK text; duplicate keys; deeply nested object (depth 500).

### 4.2 `score.py` (DET-6, C7–C9)

| ID | P | Layer | Test | Expected |
|---|---|---|---|---|
| QA-DET-11 | P0 | unit | All 10 rows of prd §6.6 (parametrized) | Confidence equal to 2 decimals; same risk |
| QA-DET-12 | P0 | unit | Threshold edges: 0.399, 0.400, 0.749, 0.750 | low, watch, watch, danger |
| QA-DET-13 | P0 | unit | G1: authority clear + urgency clear + 2 broken rules (conf ≥ 0.75) | Capped at `watch` |
| QA-DET-14 | P0 | unit | G2: threat + secrecy + inside_knowledge (no authority, no ask, no rule), conf ≥ 0.75 | `watch`, confidence 0.74 |
| QA-DET-15 | P0 | unit | G2 trio: authority + secrecy + threat, no ask | `danger` allowed |
| QA-DET-16 | P0 | unit | G3: only `phrase` evidence, conf ≥ 0.75 | Capped at `watch` |
| QA-DET-17 | P0 | unit | G4: S1-beat-3 evidence but all `speaker: "you"` | Confidence 0, `low` |
| QA-DET-18 | P0 | unit | G5: model failure, no phrase evidence | `low`, confidence 0, `source: "fallback"`, reason says the check failed |
| QA-DET-19 | P0 | unit | Caps: 5 combos → +0.25; 4 rules → +0.30; 4 safe signals → −0.30; result clamped to [0, 1] | Caps hold |
| QA-DET-20 | P0 | unit | Two `authority` items (hint, clear) | Uses clear (max per tactic) |
| QA-DET-21 | P1 | unit | Phrase + model agree on a tactic | model value + 0.05, max 0.95 |
| QA-DET-22 | P0 | unit | Every tactic in `TACTICS` has a weight; no weight for an unknown tactic | Ties score.py to contracts |
| QA-DET-23 | P0 | unit | Risk and confidence never disagree: 1 000 random evidence sets | `risk == level(confidence)` after guards, always |

### 4.3 `rules.py` (DET-4, C6)

| ID | P | Layer | Test | Expected |
|---|---|---|---|---|
| QA-DET-24 | P0 | unit | Each P0 rule fires on its tactic (parametrized over prd §8) | Rule id in `rules_broken` |
| QA-DET-25 | P0 | unit | `government_…` with `bank_change` and **no** `authority` | Not broken (S2 must not trip it) |
| QA-DET-26 | P0 | unit | Same with `authority` | Broken |
| QA-DET-27 | P0 | unit | `enabled: false` | Never fires |
| QA-DET-28 | P1 | unit | `keywords`: case-insensitive, caller lines only (`you: gift card` doesn't fire) | As stated |
| QA-DET-29 | P0 | unit | `rules.json` itself: unique ids, known tactics, text 1–200 chars, ≤ 30 rules | Valid |
| QA-DET-30 | P0 | unit | Tactic sets of B1–B7 (from prd §4.1) | `rules_broken == []` |

### 4.4 `ollama_client.py` and `check()` (DET-2, DET-7)

| ID | P | Layer | Test | Expected |
|---|---|---|---|---|
| QA-DET-31 | P0 | unit | Request body: URL `http://localhost:11434/api/chat`, `format: "json"`, `temperature: 0`, `stream: false`, model from `CALLGUARD_MODEL` (default `qwen2.5:7b`), timeout 8 s | As stated |
| QA-DET-32 | P0 | unit | `post` raises timeout | `check()` returns the G5 fallback, no exception |
| QA-DET-33 | P0 | unit | `post` raises connection refused | Same |
| QA-DET-34 | P0 | unit | `check()` on: empty window; only `you:` lines; a 10 000-char window; CJK and emoji | Always a valid `ScamCheck`; `you`-only → `low` without calling the model |
| QA-DET-35 | P0 | unit | The prompt sent to the model contains the speaker-labelled window inside clear delimiters, and the enabled rules' text | Checked on the fake's captured body |
| QA-DET-36 | P0 | unit | Prompt says the window is data, not instructions (prompt-injection defence; see eval A1) | String check on `prompt.md` |
| QA-DET-37 | P0 | privacy | Sentinel window through `check()` with `capsys`/`caplog` | Sentinel never printed; ≤ 80 chars of window in any line |
| QA-DET-38 | P0 | unit | Copy lint over `prompt.md`, fallback templates, prd §18.1 next steps used in code | No "this is fraud", "scammer", "scam call" in user-facing strings; every next step is a concrete action |
| QA-DET-39 | P0 | privacy | No network import in `callguard/detection/` (Ollama reached through the injected `post`) | Import scan |

### 4.5 Eval harness (EVAL-1..6)

The eval harness tests are specified in [eval-suite.md §9](eval-suite.md#9-requirements-eval-). Additional scripts and metrics are in [eval-suite.md §11](eval-suite.md#11-expansion-v2-adversarial-scripts-fault-injection-and-new-metrics).

---

## 5. Server

Location: `tests/server/`. Fakes: `fake_stream` (or the lane's own copy), a fake `check()` that returns scripted `ScamCheck`s, a fake HTTP transport for `egress.py`, a fake clock, and a fake `webview` module. Use FastAPI's `TestClient` for WebSocket tests.

### 5.1 App and WebSocket (SRV-1, SRV-6)

| ID | P | Layer | Test | Expected |
|---|---|---|---|---|
| QA-SRV-01 | P0 | unit | `GET /` | 200, serves `ui/index.html` (or a placeholder while `ui/` is empty) |
| QA-SRV-02 | P0 | unit | Connect to `/ws` | First message is `status`; then `rules` (once SRV-14/DET-4 exist) |
| QA-SRV-03 | P0 | unit | Every message sent during a fake S1 call | Exactly `{type, data}`, `type ∈ MessageType`, `data` has the contract's required keys |
| QA-SRV-04 | P0 | unit | Two clients connected | Both receive every broadcast |
| QA-SRV-05 | P0 | unit | Client sends malformed JSON, an unknown `type`, or `gate_release` with an unknown `how` | Ignored, logged without content, connection stays open |
| QA-SRV-06 | P0 | unit | Client disconnects and reconnects mid-call | Gets `status`, `call: started`, current call risk and gate state again (prd §16) |
| QA-SRV-07 | P0 | unit | Client disconnects during a broadcast | No exception kills the pipeline |

### 5.2 Pipeline (SRV-2, SRV-4)

| ID | P | Layer | Test | Expected |
|---|---|---|---|---|
| QA-SRV-08 | P0 | unit | `--fake s1_government.txt --fake-speed 0` with fake check | `call: started`, `transcript` per line, `check` per caller line, ends in `danger`, then `call: ended` |
| QA-SRV-09 | P0 | unit | Rolling window: lines whose `end` is older than 30 s are dropped; lines are `caller: …` / `you: …` | Window content checked on the fake's input |
| QA-SRV-10 | P0 | unit | `you:` chunk | Pushed as `transcript`, does **not** trigger `check()` |
| QA-SRV-11 | P0 | unit | Skip if busy: fake check takes 2 s, chunks arrive every 0.1 s | At most one `check()` running; exactly one rerun after it finishes, with the latest window |
| QA-SRV-12 | P0 | unit | `check()` raises | Pipeline keeps going, sends nothing broken, next chunk triggers a fresh check |
| QA-SRV-13 | P0 | privacy | Latency log line | Has milliseconds, no transcript text |

### 5.3 Call-risk smoothing (SRV-7, C10)

| ID | P | Layer | Test | Expected |
|---|---|---|---|---|
| QA-SRV-14 | P0 | unit | low → danger | Shown immediately |
| QA-SRV-15 | P0 | unit | danger, then 10 × low | Still danger (sticky) |
| QA-SRV-16 | P0 | unit | watch, low, low, low | low after exactly the 3rd low |
| QA-SRV-17 | P0 | unit | watch, low, low, watch, low, low | Still watch (counter resets) |
| QA-SRV-18 | P0 | unit | danger 0.86, then danger 0.99, then danger 0.80 | Shows 0.99 with that check's tactics and evidence |
| QA-SRV-19 | P0 | unit | danger, then `mark_safe` / `gate_release` (each `how`) | Released as prd §6.7 and §7.4 say; `mark_safe` → low |
| QA-SRV-20 | P0 | unit | Call ends | State reset; next call starts at low |
| QA-SRV-21 | P1 | unit | The smoothing function is pure (`smooth(state, check) -> state`) and importable by the eval | Same results as the eval's copy (eval-suite N2) |

### 5.4 Call lifecycle (SRV-5)

| ID | P | Layer | Test | Expected |
|---|---|---|---|---|
| QA-SRV-22 | P0 | privacy | Sentinel call, then `end_call` | No object reachable from the app holds the sentinel (walk `gc.get_objects()` strings, or inspect window/history/cache explicitly) |
| QA-SRV-23 | P0 | unit | `end_call` | `call: ended` sent; window, check history, verify cache and gate cleared |
| QA-SRV-24 | P0 | unit | Two calls in a row naming the same org | Searched once in **each** call (cache is per call) |
| QA-SRV-25 | P0 | unit | App shutdown during a call | Same clearing as `end_call` |

### 5.5 Egress (SRV-3, C16)

| ID | P | Layer | Test | Expected |
|---|---|---|---|---|
| QA-SRV-26 | P0 | unit | Entry recorded **before** the request: the fake transport asserts the entry already exists when it is called | Order holds |
| QA-SRV-27 | P0 | unit | Transport raises a connect error | `status: "offline"`, no exception, `verify` with `status: "offline"` |
| QA-SRV-28 | P0 | unit | Transport returns 500 or invalid JSON | `status: "error"`, `verify` `status: "error"` |
| QA-SRV-29 | P0 | unit | Entry fields | `time` ISO local; `destination` host only (no path, no query string); `sent` = exact query |
| QA-SRV-30 | P0 | privacy | API key | Never in an `EgressEntry`, a log line or a WebSocket message |
| QA-SRV-31 | P0 | privacy | `local_ollama_post` with `localhost`, `127.0.0.1` | Allowed, **no** egress entry |
| QA-SRV-32 | P0 | privacy | `local_ollama_post` with `localhost.evil.com`, `127.0.0.1.nip.io`, `10.0.0.5`, `http://[::ffff:8.8.8.8]` | Refused |
| QA-SRV-33 | P0 | unit | `online()` result is cached for 15 s (fake clock) | One probe per 15 s |

### 5.6 `safe_org()` (SRV-8, prd §11.1)

Window for these cases: `caller: Hi, this is Officer John Chen from the Department of Justice and the IRS.` and `you: I work at Pearson Hale LLP.` Never-search list: `Pearson Hale LLP, David Park, Brightline Supplies`.

| ID | P | Input | Expected | Why |
|---|---|---|---|---|
| QA-SRV-34 | P0 | `Department of Justice` | accept | Org word, in caller lines |
| QA-SRV-35 | P0 | `IRS` | accept | Known acronym, in caller lines |
| QA-SRV-36 | P0 | `John Chen` / `Officer John Chen` | refuse | Person's name |
| QA-SRV-37 | P0 | `Department of Justice case 4471` | refuse | Digits |
| QA-SRV-38 | P0 | `help@doj.gov`, `www.justice.gov`, `justice.com`, `http://x` | refuse | Email / domain / link |
| QA-SRV-39 | P0 | 7-word name; a 61-char name | refuse | Length limits |
| QA-SRV-40 | P0 | `Pearson Hale LLP` | refuse | Only in a `you:` line, and on never-search |
| QA-SRV-41 | P0 | `Federal Bureau of Investigation` | refuse | Not in the window (model invented it) |
| QA-SRV-42 | P0 | `department of justice` (case differs from window) | accept | Match is case-insensitive |
| QA-SRV-43 | P0 | `brightline supplies` said by the caller | refuse | Never-search, case-insensitive |
| QA-SRV-44 | P0 | Any refusal | Transport **not** called; egress entry `status: "refused"`, `sent: ""`; `verify` says lookup skipped | prd §11.1 |
| QA-SRV-45 | P0 | Accepted name | Query is exactly the name (C12) or exactly `"{org}" impersonation scam` (C17); nothing appended | Guardrail 3 |
| QA-SRV-46 | P0 | `search()` called directly with > 80 chars or a newline | Refused (SRV-12c) | Defence in depth |

### 5.7 Surge lookup (SRV-8, C12)

| ID | P | Layer | Test | Expected |
|---|---|---|---|---|
| QA-SRV-47 | P0 | unit | `claimed_identity` set at confidence 0.39 | No search |
| QA-SRV-48 | P0 | unit | Same at 0.40 | One search |
| QA-SRV-49 | P0 | unit | Same org in 6 consecutive checks | One search per call |
| QA-SRV-50 | P0 | unit | Fake Tavily response with a phone and URL | `verify` has `phone`, `source_url`, `status: "ok"` |
| QA-SRV-51 | P0 | unit | Response with no phone | `verify` `status: "not_found"` |
| QA-SRV-52 | P0 | unit | Tavily errors, Exa answers | Two egress entries (error, ok); `verify` from Exa |
| QA-SRV-53 | P0 | unit | No keys in the environment | No request, `status: "error"`, no crash |
| QA-SRV-54 | P0 | unit | Fake B1, B2, B3, B7 runs | Egress log empty (prd §11 "egress stays empty on benign calls") |

### 5.8 Safe-path pause (SRV-9, prd §7.4)

| ID | P | Layer | Test | Expected |
|---|---|---|---|---|
| QA-SRV-55 | P0 | unit | Every transition in the §7.4 diagram (parametrized table of state, event, next state) | All match |
| QA-SRV-56 | P0 | unit | danger, confidence 0.84, ask tactic | `armed`, not `locked` |
| QA-SRV-57 | P0 | unit | danger, confidence 0.85, no ask tactic (authority + secrecy + threat trio) | `armed` only |
| QA-SRV-58 | P0 | unit | Off → Locked in one step (0.99 + `credential_request`) | `locked` |
| QA-SRV-59 | P0 | unit | `CALLGUARD_GATE=off` | Never `locked`; `status.gate == "off"` |
| QA-SRV-60 | P0 | unit | Locked, fake clock +120 s | Released; `release_in` counts down in `gate` messages |
| QA-SRV-61 | P0 | unit | Released, then the same ask tactic again | Stays released (no re-nag) |
| QA-SRV-62 | P0 | unit | Released, then a **new** ask tactic | `locked` again |
| QA-SRV-63 | P0 | unit | Locked, call ends | `off` |

### 5.9 Colleague and mark safe (SRV-13)

| ID | P | Layer | Test | Expected |
|---|---|---|---|---|
| QA-SRV-64 | P0 | privacy | `colleague` during a sentinel call | `osascript` (patched) called once with the fixed heads-up text; no sentinel, no claimed identity, no number in it |
| QA-SRV-65 | P0 | unit | `mark_safe` | Call risk `low`, gate released, a `check`/`gate` update sent |

### 5.10 Server privacy (SRV-12)

| ID | P | Layer | Test | Expected |
|---|---|---|---|---|
| QA-SRV-66 | P0 | privacy | AST import scan (SRV-12a) | As QA-SH-05 |
| QA-SRV-67 | P0 | privacy | Full fake S1 call with `open` (write modes) and `os.write` patched | Zero writes (SRV-12b) |
| QA-SRV-68 | P0 | privacy | Full fake S1 call with a sentinel; scan `capsys`, `caplog`, every WebSocket message except `transcript`/`check`, every egress entry | Sentinel only in `transcript` and `check.evidence`; never in logs or egress |
| QA-SRV-69 | P0 | privacy | Debug logging on | No log line contains > 80 consecutive chars of any script line |

### 5.11 Window (SRV-11)

| ID | P | Layer | Test | Expected |
|---|---|---|---|---|
| QA-SRV-70 | P0 | unit | `--browser` | `webview` never imported |
| QA-SRV-71 | P0 | unit | Default start with a fake `webview` | `create_window(title="Callguard", on_top=True, …)`, `webview.start()` on the main thread, uvicorn on a background thread |
| QA-SRV-72 | P0 | unit | `danger` arrives | Window brought to front (fake records the call); never full-screen |
| QA-SRV-M1 | P0 | manual | `python -m callguard.server` on the Mac | Native window, no browser tab, stays above Zoom |
| QA-SRV-M2 | P0 | manual | During the pause, type in Notes and Chrome | Typing works everywhere (prd §7.5) |

---

## 6. UI

Location: `tests/ui/` plus `ui/dev/replay.html`. The UI has no build step, so tests drive `replay.html` with Playwright (Python) when it is installed and skip otherwise. Every case runs from a JSON fixture of WebSocket messages, no Server needed. Fixtures: `s1`, `s2`, `b3`, `offline`, `model_down`, plus the ones named below.

### 6.1 States and meter (UI-1, UI-2, UI-3)

| ID | P | Fixture | Test | Expected |
|---|---|---|---|---|
| QA-UI-01 | P0 | none | Idle | "Not on a call", grey meter, "Nothing has left this device" |
| QA-UI-02 | P0 | `s1` | Meter low → watch → danger | Each level has a word **and** an icon, not only a colour |
| QA-UI-03 | P0 | crafted | Confidence 0.29, 0.31, 0.71, 0.79, 0.99 | Bar 3/10 "No clear signs", 3/10, 7/10 "Some signs", 8/10 "Strong signs", 10/10; never a % |
| QA-UI-04 | P0 | `s1` | Watch note | `reason` plus chips in plain words (prd §6.3); a chip expands to its `evidence.quote` |
| QA-UI-05 | P0 | crafted | `rules_broken` at watch | Rule text shown on the watch note |
| QA-UI-06 | P0 | `v1_check` | A `check` with no `confidence`, `evidence`, `safe_signals`, `source` | Renders; no `undefined`, no crash |
| QA-UI-07 | P0 | crafted | Unknown tactic string `"fear"` | Ignored or shown raw; no crash |
| QA-UI-08 | P0 | `model_down` | `status.model: "degraded"` | Banner "Basic checks only, local model unavailable" |

### 6.2 Danger, notification and pause (UI-4, UI-5)

| ID | P | Fixture | Test | Expected |
|---|---|---|---|---|
| QA-UI-09 | P0 | `s1` | Danger | Overlay opens with claimed identity, tactics with quotes, rule text, verify line, `next_step`; sound plays |
| QA-UI-10 | P0 | `s1` | Notification (stub `window.Notification`) | Title and body are the fixed copy only; no quote, no org, no digits (prd §9.5) |
| QA-UI-11 | P0 | `s1_two_asks` | Notifications | One at first danger, one more only for a new ask tactic; `tag: "callguard-danger"` |
| QA-UI-12 | P0 | `s1` | Pause open: press Enter, Esc, Space on the overlay | Overlay stays |
| QA-UI-13 | P0 | `s1` | Focus on open | Primary "Hang up and call back" button |
| QA-UI-14 | P0 | `s1` | Type `SAFE`, hold 2.9 s, release | Nothing sent |
| QA-UI-15 | P0 | `s1` | Type `SAFE`, hold 3 s | `gate_release` with `how: "mark_safe"` sent |
| QA-UI-16 | P0 | `s1` | Type `SAF`, hold 3 s | Nothing sent; hold button disabled until the text matches |
| QA-UI-17 | P0 | `s1` | "Hang up and call back" / "Check with a colleague" (keyboard only) | `gate_release` with `hang_up` / `colleague` |
| QA-UI-18 | P0 | `s1` | Countdown | Starts at `gate.release_in`, steps back to the red side panel at 0 |
| QA-UI-19 | P0 | crafted | Verify line variants: ok, offline, not_found, error, none yet | Number + source domain; "Offline, search skipped"; "Couldn't find a public number, use the one on file"; same for error; "Looking up…" |

### 6.3 Egress panel, transcript and connection (UI-6, UI-7)

| ID | P | Fixture | Test | Expected |
|---|---|---|---|---|
| QA-UI-20 | P0 | `s1` | Egress entry | Time, destination, the exact `sent` text, status |
| QA-UI-21 | P0 | `refused` | `status: "refused"` | "Blocked: lookup skipped to protect your privacy" |
| QA-UI-22 | P0 | `s1` | Transcript tail | Last ~3 lines, speaker-tagged |
| QA-UI-23 | P0 | `s1` | `call: ended` | Transcript tail empty; no transcript text anywhere in the DOM (`document.body.innerText` has no script line) |
| QA-UI-24 | P0 | crafted | WebSocket closes | "Reconnecting…" shown, retries with backoff, recovers when the server is back |
| QA-UI-25 | P0 | `offline` | Status offline | Grey dot "Offline" |

### 6.4 UI safety and quality

| ID | P | Layer | Test | Expected |
|---|---|---|---|---|
| QA-UI-26 | P0 | unit | XSS: transcript text, `reason`, quote and org set to `<img src=x onerror=window.__pwned=1>` | Rendered as text; `window.__pwned` undefined (use `textContent`, never `innerHTML` with data) |
| QA-UI-27 | P0 | unit | 300-char `reason`, 80-char quotes, 6-word org at 380 px wide | Wraps, no horizontal scroll, buttons visible |
| QA-UI-28 | P0 | lint | Grep `ui/` for `http://` / `https://` script or style sources | None (no CDN, works offline) |
| QA-UI-29 | P0 | lint | Grep `ui/` for `localStorage`, `sessionStorage`, `indexedDB` holding transcript or check data | None |
| QA-UI-30 | P0 | lint | Copy lint over `ui/` | No "fraud", "scammer"; "verify" appears on the overlay |
| QA-UI-31 | P1 | unit | Accessibility: every button reachable by Tab, meter has `aria-live="polite"`, overlay has `role="alertdialog"` | As stated |
| QA-UI-M1 | P0 | manual | Projector check: read the danger headline and the number from the back of the room | Legible |

---

## 7. End to end (integration)

Run at each checkpoint (Sat 19:00, 22:00, Sun 09:00) on `main`, on the demo Mac, with Ollama running. Extends prd §14.3.

| ID | P | Test | Expected |
|---|---|---|---|
| QA-E2E-01 | P0 | `pytest` on `main`, Wi-Fi off | All green |
| QA-E2E-02 | P0 | `--fake s1_government.txt` | low → watch → danger at beat 3; pause at beat 4; egress shows exactly one entry: `Department of Justice` |
| QA-E2E-03 | P0 | `--fake` with each of S2, S3, S4 | danger at the giveaway beat; pause at the 🔒 beat |
| QA-E2E-04 | P0 | `--fake` with each of B1, B2, B3, B7 | Never danger; B1, B2, B7 low; egress empty |
| QA-E2E-05 | P0 | L3 timing: giveaway line spoken on Zoom → danger on screen | ≤ 10 s, measured 3 times |
| QA-E2E-06 | P0 | Wi-Fi off, cold start (reboot, launch, run S2) | danger; verify "Offline, search skipped"; egress entry `offline` |
| QA-E2E-07 | P0 | Danger, then "Hang up and call back" | Pause released, meter stays red until call end |
| QA-E2E-08 | P0 | End the call in Callguard during danger, start a new fake call with B1 | New call starts low; no old transcript visible |
| QA-E2E-09 | P0 | Kill Ollama mid-call, then restart it | "Basic checks only" banner; no crash; checks resume after restart |
| QA-E2E-10 | P0 | Close and reopen the window mid-call (or reload in `--browser`) | State restored from the server |
| QA-E2E-11 | P0 | 15-minute benign Zoom call (normal team chat) | Never danger; at most brief watch; memory flat |
| QA-E2E-12 | P0 | After the whole run: search the disk for the sentinel and for script sentences (`grep -r` in `~`, `/tmp`, `~/Library/Logs`, notification DB) | Not found |
| QA-E2E-13 | P1 | `--fake` with the eval-suite §11 adversarial set (A1–A6, B8–B11) | Matches each script's `expect` |
| QA-E2E-14 | P0 | During the pause, type in another app | Works (nothing blocked) |

---

## 8. Failure-mode matrix

Every row of prd §16 has at least one automated test and one manual check.

| prd §16 failure | Automated | Manual |
|---|---|---|
| Ollama not running / model missing | QA-DET-33, QA-UI-08 | QA-E2E-09 |
| Model returns bad JSON | QA-DET-02 | eval §11.2 fault fixtures |
| Model slower than 8 s | QA-DET-32, QA-SRV-11 | — |
| Whisper mishears a key phrase | eval `__mishear` variants | QA-AUD-M2 |
| BlackHole missing / output switched | QA-AUD-12 | QA-AUD-M7 |
| Wi-Fi off | QA-SRV-27, QA-UI-25 | QA-E2E-06 |
| Search API error / no phone found | QA-SRV-28, 51, 52, QA-UI-19 | — |
| UI disconnects | QA-SRV-06, QA-UI-24 | QA-E2E-10 |

---

## 9. Demo-day QA run

Sun 08:00, before the backup video (Sun 09:00). All on the demo Mac, Wi-Fi as it will be on stage.

1. `git log -1` on `main` matches the commit Coco tagged for the demo.
2. `pytest`: all green.
3. `python -m callguard.detection.eval --set p0 --runs 3`: `P0 GATE PASS`, plus the demo gate in eval-suite §11.4.
4. QA-E2E-02 to 07 in order, then QA-E2E-12 (disk sweep).
5. Notification permission granted, sound on, volume up, Do Not Disturb **off**.
6. Rehearse the exact demo script once end to end; record the backup video from that run.

---

## 10. Gaps and decisions found while writing this

These are spec gaps the tests exposed. Each needs a one-line decision from Coco; until then the test is marked `xfail` with the question in its reason.

| # | Gap | Where | Proposal |
|---|---|---|---|
| G-1 | **Single first names pass `safe_org()`.** S4's caller says "it's David"; if the model sets `claimed_identity: "David"`, it is one capitalised word, so the person-name check (2–3 words) doesn't catch it, and it would be searched | prd §11.1 | Refuse a single word unless it is an all-caps acronym (`IRS`, `FBI`) or contains an org word; add QA-SRV-34b |
| G-2 | **Does the `online()` probe need an egress entry?** It is a network call, and guardrail 2 says every call records one; logging it every 15 s floods the panel | prd C16, guardrail 2 | Probe a host with no payload (e.g. `HEAD` to the search API host), record it once per state change (online ↔ offline), not every probe |
| G-3 | **Evidence-quote matching rule.** "Verbatim" breaks when Whisper and the model differ by case or spaces | prd C5 | Compare after lowercasing and collapsing whitespace (QA-DET-05) |
| G-4 | **A caller-supplied callback number is not a safe signal.** "Call me back on 555-0142" sounds like `callback_known_number` but is the scammer's own number | prd §6.2, C8 | Prompt and score: only a number the user already has (on file, on the card, public site) counts; eval A2 tests it |
| G-5 | **Is `SAFE` case-sensitive?** | prd §7.2 | Accept any case (`safe`), since the friction is the 3 s hold, not typing |
| G-6 | **Which sticky-danger releases apply?** §6.7 says danger stays "until the user taps an action"; §7.4 releases the gate on hang up / colleague too. Does the meter also drop on hang up? | prd §6.7 vs §7.4 | Gate releases on any action; meter drops to low only on `mark_safe` or call end |
| G-8 | **A bare code request can't reach danger.** `credential_request` (clear, 0.54) + its rule (+0.15) = 0.69 → `watch`. If the authority line has slid out of the 30 s window (eval A3), the request for an MFA code only shows amber | prd §6.3–6.5 | Either keep "ask" tactics sticky in the call state (Server keeps the tactics seen this call), or add a floor: an ask tactic + a broken rule → at least 0.75. The first is simpler and also helps A6 |
| G-7 | **Org dedupe across spellings.** "the IRS", "IRS", "Internal Revenue Service" | SRV-8 | Normalise case and a leading "the"; treat different names as different orgs (at most 2–3 searches per call is fine) |

---

## 11. Prompt snippet to hand each agent

Append to the lane's starting prompt:

```
QA: implement every QA-<LANE>-NN case for your lane from hack1984/qa-test-plan.md
(P0 first) in tests/<lane>/, named test_qa_<lane>_<nn>_<short_name>. Tests must pass
offline with no Ollama and no audio devices. If a case is blocked by a gap in §10,
mark it xfail with the gap id in the reason. Report "QA: x/y P0 green" in every Status line.
Never weaken a test to make it pass; if you think a case is wrong, say so under Needs.
```
