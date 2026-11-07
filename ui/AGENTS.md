# Lane: UI + demo

Read the root [AGENTS.md](../AGENTS.md) first. You own `ui/` and `tests/ui/` only.

## Delivers
A local web page (`ui/index.html` plus plain JS and CSS, no build step) served by the Server. It sits in a narrow window next to Zoom and reacts to the WebSocket messages in root AGENTS.md section 3.

## Tasks
Full list with IDs and "done when": [prd.md §13.5](../hack1984/prd.md#135-ui--ui-testsui).
Full flows and copy-paste task prompts (T1–T11, design brief): [hack1984/ui-flows.md](../hack1984/ui-flows.md), [hack1984/ui-tasks.md](../hack1984/ui-tasks.md). Work them in order.

**P0**
- [ ] "Listening locally" badge, and an online/offline indicator from `status`
- [ ] Risk meter: low / watch / danger
- [ ] "Watch" note: one line with `reason`
- [ ] Danger notification (UI-4, [prd.md §9.5](../hack1984/prd.md#95-the-danger-notification)): browser Notification API with a sound; fixed text only, never the caller's words, a name or a number; clicking it focuses the page and shows the danger warning
- [ ] Danger warning in the Callguard window, not full-screen (UI-4): tactic, the caller's words, rule broken, real number (from `verify`), `next_step`
- [ ] Safe-path pause exits (UI-5): "Hang up and call back", "Check with a colleague", type `SAFE` + hold 3 s. Never blocks typing in other apps
- [ ] "What left this device" panel listing every `egress` message (empty is the point); `refused` entries show "Blocked: lookup skipped to protect your privacy"
- [ ] Until the Server is ready, test with a fake WebSocket or a local JSON replay

**P1**
- [ ] "Check with a colleague" and "Mark as safe" buttons
- [ ] Firm rules panel (UI-13), then the rules editor with a "Never search for" list (UI-14, [prd.md §8.1](../hack1984/prd.md#81-customizing-the-rules-p1)); editing is locked during a call
- [ ] "Say this" line on the watch note and danger warning (UI-15, wording in [prd.md §18.3](../hack1984/prd.md#183-say-this-lines))
- [ ] Scam report line on the danger warning from `verify.report` (UI-16)

**P2**
- [ ] Post-call summary card (UI-10): evidence quotes with time and tactic, "Copy for a report"; memory only, never the full transcript, gone when dismissed

**Demo (owner of the backup)**
- [ ] Record the backup video of the full demo by **Sun 09:00**
- [ ] Keep the demo machine's setup steps in `ui/DEMO.md`

## Rules for this lane
- Plain words that a paralegal understands. Say "verify first," not "fraud"
- Never show or keep more transcript than the current call needs
- No external fonts, CDNs or analytics. The page must work with the Wi-Fi off

## Status
- [Sat 21:50] Done: visual prototype `ui/dev/prototype.html` (7 states, light + dark) for sign-off; T1 in progress (fixtures in `ui/dev/fixtures/`, `ui/ws.js`; replay.html and tests not yet written) | Next: finish T1 after Coco signs off on the look | Needs: `pytest` pinned in requirements.txt (Coco); rules.json text for S1's "bank details" ask (no bank-details tactic yet; fixtures use personal_data_request) (Detection)
- [Sat 23:30] Done: prototype v3 signed off by Coco (4 sections: status, why, what to do, actions; black primary pill; "Say this" from prd 18.3). T1 / UI-8: 11 fixtures on contracts v2 (`ui/dev/fixtures/`), replay harness `ui/dev/replay.html` (picker, play/pause, step, 0.5/1/4x, restart, drop connection, Server→UI and UI→Server logs), `ui/ws.js` (?ws=fake / ?ws=url, reconnect every 2 s), `ui/app.js` with the single `onMessage({type, data})` dispatch and a plain placeholder render, tests in `tests/ui/` (65 pass). Checked in Chromium: every fixture plays to the end with no dropped messages, all 4 client messages reach the log, reconnect recovers | Next: T2 shell built to prototype v3; replace "Typing paused" copy with the new safe-path pause copy (prd 7.6) | Needs: (Coco) plain `pytest` at the repo root fails to collect `hack1984/continuity-audio-test/test_capture.py` (no `sounddevice`); add `testpaths = tests` in a root pytest.ini or importorskip it. (Coco) `requirements.txt` with `pytest` pinned. (Detection) S1's bank-details ask has no tactic of its own; fixtures use `personal_data_request`.
- [Sun 00:15] Done: T2 / UI-1 shell built to prototype v3. `ui/styles.css` tokens (light + dark via prefers-color-scheme, reduced motion, 2 px focus ring, system font only); `ui/index.html` regions (header, consent line with "Why?" details and memory-only dismiss, banners, status hero, Why / What to do / Latest slots, actions slot, privacy line); `ui/view.js` renders state, `ui/app.js` keeps the single `onMessage` dispatch. Header: "Listening locally · nothing stored" / "Not listening", Online / Offline, "Pause on" when `status.gate` is on. Banners: "Connecting to Callguard…" while the socket is closed (reconnects every 2 s), "Basic checks only, local model unavailable" for model degraded/offline. Privacy line counts only egress that actually went out (ok, error); offline/refused show as "N skipped". Checked in Chromium: idle, offline, model_down, drop + recover, light + dark at 360 px, no horizontal scroll at 320 px. 70 UI tests pass | Next: T3 (signs bar, Why pills, "See what they said", Say this) | Needs: (Coco) repo-root `pytest` still fails to collect: tests/server needs `httpx`, hack1984/continuity-audio-test needs `sounddevice`, and there is no `requirements.txt`; `pytest tests/ui` passes.
