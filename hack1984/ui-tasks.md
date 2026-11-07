# Callguard UI: design brief and agent task prompts

Owner: Coco (Lead). For the UI lane agent (`lane/ui`, folder `ui/`, tests in `tests/ui/`).
Read with: [ui-flows.md](ui-flows.md) (the flows these tasks build), [prd.md](prd.md) §9 and §13.5.

How to use this file: give the agent **Part A (design brief)** once, then one **Part B task prompt** at a time, in order. Each task is one PR-sized change Coco can review on its own. Each prompt is self-contained and can be pasted as is.

---

## Part A. Design brief (paste at the top of every UI session)

```text
You are the UI lane agent for Callguard. Read /AGENTS.md, then ui/AGENTS.md,
then hack1984/ui-flows.md. You own ui/ and tests/ui/ only. Never edit other lanes,
callguard/shared/contracts.py, or root AGENTS.md; write what you need under Needs
in ui/AGENTS.md Status.

PRODUCT
Callguard is a narrow (~360 px) always-on-top window beside a Zoom call on a
13" MacBook. It warns a paralegal, in plain words, when a call follows a scam
script, and proves nothing about the call leaves the laptop. Users glance at it
for under a second: every state must read in one glance as colour + icon + one word.

TECH CONSTRAINTS (hard)
- ui/index.html + plain ES modules + one CSS file. No build step, no npm, no
  framework, no CDN, no web fonts, no analytics. Must work with Wi-Fi off.
- Use the system font stack: -apple-system, BlinkMacSystemFont, "Helvetica Neue", sans-serif.
- Connect to ws://localhost:8000/ws (or ?ws= query override for the replay harness).
  Messages are {"type", "data"} as in AGENTS.md §3 and prd.md §12.
- Treat all v2 fields (confidence, evidence, gate, call, rules, status.model,
  verify.status) as optional. Render sensibly without them.
- Never write transcript text to localStorage, sessionStorage, IndexedDB, cookies,
  console.log (except the last 80 chars), or any request. Keep only the last 3 lines
  in memory, and delete them on call ended.

VISUAL LANGUAGE
- Calm by default. Low risk is quiet: mostly neutral greys, a small green mark.
- Three risk levels, each with colour, icon and word (colour is never alone):
    low     green   ✓  "Low"     "No clear signs"
    watch   amber   ◐  "Watch"   "Some signs"
    danger  red     ⚠  "Danger"  "Strong signs"
  Idle is grey ○ "Not on a call".
- Confidence = words + 10-segment bar. Never a percentage, never "fraud probability".
  0-3 segments "No clear signs", 4-7 "Some signs", 8-10 "Strong signs".
- Define tokens once in :root (--bg, --surface, --text, --muted, --border,
  --low, --watch, --danger, --idle, --focus, radii, spacing 4/8/12/16/24).
  Support light and dark via prefers-color-scheme. All text >= 4.5:1 contrast.
- Type scale: 13 px body, 12 px meta, 15 px level word, 22-28 px overlay headline.
- Motion: 150 ms transitions only; respect prefers-reduced-motion. The only
  attention grabs are the danger overlay opening (one short sound) and a single
  flash of the egress header when an entry arrives.
- Focus ring always visible (2 px --focus). Every control reachable by keyboard.

COPY RULES (prd.md §9.3)
- Say "verify first", "check", "stop and verify". Never "fraud", "scam",
  "scammer", "attack" in UI copy.
- Every warning ends with one concrete next step, with a phone number if we have one.
- Tactic chips use these exact plain words:
    authority             Claims to be an official or someone senior
    secrecy               Asks you to keep it secret
    urgency               Rushing you
    threat                Threatens you or the firm
    credential_request    Asks for a code or password
    bank_change           Wants to change bank details
    bypass_approval       Wants you to skip the usual approval
    payment_request       Asks you to send money
    remote_access         Asks you to install software or give screen access
    personal_data_request Asks for client or personal data
    inside_knowledge      Uses real details to sound legitimate
  Unknown tactic ids: show the id with underscores replaced by spaces.

WORKING RULES
- git rebase main before each task. Small commits on lane/ui.
- Tests in tests/ui/ must pass with plain `pytest` (no browser required for the
  default run; Playwright tests, if any, skip cleanly when no browser is present).
- After each task add a Status line in ui/AGENTS.md:
  - [Day HH:MM] Done: … | Next: … | Needs: …
  then stop and tell Coco what to review.
```

---

## Part B. Tasks (in build order)

| # | Task | PRD IDs | Flows | P | Depends on |
|---|---|---|---|---|---|
| T1 | Replay harness + fixtures | UI-8 | all | P0 | — |
| T2 | Shell, tokens, header, connection | UI-1 | F0, F7, F8 | P0 | T1 |
| T3 | Risk meter + watch note + chips | UI-2, UI-3 | F1, F2 | P0 | T2 |
| T4 | Transcript tail + call lifecycle | UI-7 | F1, F9 | P0 | T2 |
| T5 | "What left this device" panel | UI-6 | F6, F7 | P0 | T2 |
| T6 | Danger overlay | UI-4 | F3 | P0 | T3 |
| T7 | Gate lock + three exits | UI-5 | F4, F5 | P0 | T6 |
| T8 | Polish pass on the demo path + a11y audit | UI-1..7 | §5 demo path | P0 | T2–T7 |
| T9 | `ui/DEMO.md` + backup video | UI-11 | demo | P0 | T8 |
| T10 | Side buttons + rules panel | UI-9, UI-13 | F10, F11 | P1 | T3 |
| T11 | Post-call summary card | UI-10 | F9 | P2 | T4 |

Suggested timing (PRD §10.9): T1–T5 by Sat 19:00 first full run; T6–T8 by Sat 22:00; T10 Sat 22:00–Sun 02:00 if P0 is green; T9 Sun 07:00–09:00.

---

### T1. Replay harness and fixtures (UI-8)

```text
Task T1 (UI-8): build the replay harness so every other UI task can be built
and reviewed without the Server, Ollama or a call.

Build:
1. ui/dev/fixtures/*.json. Each file is
   {"id": "...", "description": "...", "steps": [{"at": 0.0, "msg": {"type": ..., "data": ...}}, ...]}
   where "at" is seconds from start. Write these fixtures from prd.md §4.2 and
   §6.6 (use the listed confidence values and quotes verbatim):
     idle.json, s1_government.json, s2_vendor_bank.json, s3_it_code.json,
     s4_partner_wire.json, b1_vendor_invoice.json, b2_colleague.json,
     b3_real_bank.json, b7_you_say_it.json, offline.json, model_down.json
   Each call fixture: status → call started → transcript/check beats →
   verify/egress where expected → gate locked where the 🔒 beat is → call ended.
   offline.json = S1 with status.online false, verify.status "offline",
   egress.status "offline". model_down.json = S1 with status.model "degraded",
   checks capped at watch, source "fallback" on one check.
   Include a "rules" message near the start of each call fixture with the five
   P0 rules from prd.md §8.
2. ui/dev/replay.html: loads ui/index.html in an iframe (or same page) and
   feeds it fixture messages through a fake WebSocket (inject a FakeSocket
   class via ?ws=fake). Controls: fixture picker, play/pause, step, speed
   (0.5x/1x/4x), restart. Shows a log of messages sent by the UI
   (colleague, mark_safe, gate_release, end_call) so exits can be checked.
3. tests/ui/test_fixtures.py: every fixture is valid JSON, steps are sorted by
   "at", every msg.type is a known type (contracts.MessageType plus v2 types
   gate, call, rules), every fixture except idle ends with call ended, and no
   transcript text in any fixture exceeds 200 chars.

Done when: opening ui/dev/replay.html from python -m http.server in ui/ (no
Server) plays every fixture, and pytest passes. Wire it so later tasks only
need to read messages from one dispatch function: onMessage({type, data}).
```

### T2. Shell, tokens, header and connection (UI-1)

```text
Task T2 (UI-1): the side panel shell. Flows F0, F7, F8 in hack1984/ui-flows.md.

Build in ui/index.html, ui/app.js, ui/styles.css:
1. Design tokens in :root per the design brief, light and dark.
2. Layout regions A–G from ui-flows.md §1, stacked, panel width 320–420 px,
   no horizontal scroll at 320 px.
3. Header (A): badge "● Listening locally · nothing stored" (grey "Not
   listening" when status.listening is false); online dot with word
   ("Online" / "Offline"); gate mode text if status.gate is present
   ("Typing pause: on" for soft/hard, hidden for off).
4. Consent line under the header (F0 step 2), with a "Why?" <details>.
   Dismissed state kept in memory only.
5. Banners (B): "Basic checks only, local model unavailable" when
   status.model is degraded/offline; "Connecting to Callguard…" while the
   WebSocket is closed, with reconnect every 2 s and no page reload.
6. Idle state for C, E, F, G as in ui-flows.md F0.
7. ws.js: connection + reconnect + onMessage dispatch. ?ws=fake uses T1's FakeSocket.

Done when: idle.json, offline.json and model_down.json show the right header
and banner states in replay; closing the fake socket shows the reconnect
banner and recovers. Screenshot each state at 360 px wide (light + dark) into
the PR description, not into the repo.
```

### T3. Risk meter, watch note and tactic chips (UI-2, UI-3)

```text
Task T3 (UI-2, UI-3): the risk meter and watch note. Flows F1 and F2.

Build:
1. Meter (C): icon + level word + confidence words + 10-segment bar, coloured
   by level per the design brief. Segments = round(confidence * 10). If
   confidence is missing, hide the bar and show the level word only.
2. Watch note (D), shown at watch and danger: `reason` (one line, ellipsis
   with full text on hover/focus), tactic chips in the brief's plain words.
   Each chip is a <button aria-expanded>; expanding shows the caller's quote
   from evidence[] where evidence.tactic matches, in quotes, max 80 chars.
   No quote → chip is not expandable.
3. If rules_broken is non-empty, show "Firm rule: <rule text>" under the chips
   (text from the rules message; fall back to the rule id in plain words).
4. Verify line in D: "Checking <org>'s public number…" until verify arrives;
   then "Public number: <phone> · <source host>"; offline → "Offline, search
   skipped. Use the number on file."; not_found/error → "Couldn't find a public
   number, use the one on file."
5. The UI follows `check` as sent; do not add your own smoothing.
6. No sound and no animation beyond the 150 ms colour transition at watch.

Done when: b2_colleague.json and b7_you_say_it.json never leave green;
s1_government.json reaches amber with two chips that expand to the exact
quotes; b3_real_bank.json peaks at watch. Add tests/ui/test_copy.py that
checks the tactic plain-words map in the JS matches the brief and that no UI
string contains "fraud", "scam" or "scammer" (grep ui/*.js and index.html).
```

### T4. Transcript tail and call lifecycle (UI-7)

```text
Task T4 (UI-7): transcript tail and what happens at call start/end. Flows F1, F9.

Build:
1. Tail (E): last 3 transcript chunks, each tagged "Caller" or "You"
   (different weight, not only colour). Older lines are dropped from the
   array, not hidden. Long lines wrap; max 3 visual lines per chunk.
2. call started: clear D, E, chips, overlay state; meter to low.
3. call ended: delete transcript array, current check, evidence quotes and
   verify line from JS state and DOM; meter to Idle; overlay closes. Egress
   entries are kept (they hold only org names) under "Earlier today".
4. An "End call" text button in the panel footer sends {"type":"end_call"}.
5. Privacy: grep-able guarantee — no use of localStorage, sessionStorage,
   indexedDB or document.cookie anywhere in ui/ (except dev/ for the replay
   picker's last-fixture choice, if you want it).

Done when: tests/ui/test_privacy.py asserts no storage APIs in ui/*.js and
index.html, and that console.* calls never take a transcript variable without
.slice(-80). In replay, after call ended the transcript text is not found in
document.body.innerText.
```

### T5. "What left this device" panel (UI-6)

```text
Task T5 (UI-6): the egress log, the product's privacy proof. Flows F6, F7.

Build:
1. Region F header: "What left this device (N)", N = entries this session.
2. Empty state, designed not apologetic: a small lock-on-laptop glyph (inline
   SVG), "Nothing has left this device", sub-line "Your call audio and words
   stay on this laptop."
3. Each entry: local time (HH:MM:SS), destination host, exactly what was sent
   in quotes, status pill (ok / offline / error with word + colour).
   Newest first. Clicking an entry expands: "Only this text was sent: "<sent>".
   Nothing from the call itself."
4. When an entry arrives, flash the header background once (300 ms; skip
   under prefers-reduced-motion).
5. The panel is never hidden at danger level: the overlay leaves room for a
   one-line egress summary at its foot ("1 thing left this device: an
   organization name").

Done when: b1_vendor_invoice.json shows the empty state for the whole call;
s1_government.json shows exactly one entry "Department of Justice";
offline.json shows that entry with status offline.
```

### T6. Danger overlay (UI-4)

```text
Task T6 (UI-4): the danger overlay. Flow F3 and the layout in prd.md §9.4.

Build:
1. On check.risk == "danger", open an overlay covering the whole window
   (role="alertdialog", aria-labelledby the headline). If the window is wide
   (> 700 px, i.e. pywebview went full screen) centre a max 720 px card; at
   360 px it fills the panel with comfortable 16 px gutters.
2. Content, top to bottom:
   ⚠ "Stop and verify this call" + confidence bar
   "The caller claims to be: <claimed_identity>" (omit if null)
   One row per tactic: plain words + the caller's quote
   One line per broken rule: "Firm rule: <rule text>"
   Verify line (same states as T3)
   next_step in a highlighted box
   Placeholder slot for T7's lock line and exits (for now: one
   "Hang up and call back" button that only closes the overlay locally)
3. Sound: one short tone generated with the Web Audio API (no audio files),
   once per overlay open, not on every danger check.
4. Sticky: further danger checks update the content in place; the overlay
   does not close on low/watch checks; only on call ended, mark safe, or a
   release (T7).
5. Focus moves to the primary button on open; focus is trapped inside;
   Esc and Enter on the overlay background do nothing.

Done when: s1, s2, s3, s4 fixtures each open the overlay with tactic + quote +
rule (where the scenario has one) + verify line + next step; s2 shows
"Firm rule: We never change vendor or client bank details because of a phone
call…". Put light/dark screenshots of S1 at 360 px and 1280 px in the PR.
```

### T7. Gate lock and the three exits (UI-5)

```text
Task T7 (UI-5): keyboard gate UI and safe exits. Flows F4 and F5.

Build in the overlay from T6:
1. Lock line when gate.state == "locked": "🔒 Typing is paused while this call
   asks for <ask in plain words>" + mm:ss countdown from gate.release_in,
   ticking locally, re-synced on each gate message. Soft mode adds:
   "Callguard is keeping focus so you don't type it by accident."
2. Exits, in this order and weight:
   a. "Hang up and call back" — primary, large, default focus.
      Sends gate_release {how:"hang_up"}. Then shows a call-back card:
      verified number big with "Copy number" (navigator.clipboard), or
      "Use the number on file" if none.
   b. "Check with a colleague" — secondary. Sends {"type":"colleague"} then
      gate_release {how:"colleague"}. Toast: "Heads-up sent. Stay on the
      line or hang up, your choice."
   c. "I've verified, it's safe" — tertiary, small. A text input labelled
      "Type SAFE" and a hold button disabled until the input equals SAFE
      (case-insensitive). Holding (mouse or Space key down) for 3 s fills a
      progress ring; release early resets. On complete send mark_safe then
      gate_release {how:"mark_safe"}; close overlay; meter green; note
      "Marked safe".
3. Enter and Esc never trigger any exit. Tab order: a → b → input → hold.
4. When gate goes off (auto-release), remove the lock line; keep the overlay.
5. All buttons stay usable when gate is absent (pure danger, no ask).

Done when: in replay, the harness log shows exactly these client messages
for each exit; tests/ui/ has a Playwright test (skipped if no browser) that
does the whole flow keyboard-only and asserts Enter/Esc do nothing and a
2.9 s hold does not mark safe.
```

### T8. Polish pass on the demo path + accessibility audit

```text
Task T8: make every screen on the demo path (ui-flows.md §5) look finished,
then audit it.

1. Walk the demo path in replay at 360 px and full screen, light and dark.
   Fix spacing, alignment, line lengths, truncation and hierarchy until each
   screen reads in one glance from 70 cm away.
2. Check: colour is never the only signal; contrast >= 4.5:1 (3:1 for the
   bar segments); focus visible on every control; overlay announced by
   VoiceOver as an alert; reduced-motion respected.
3. Copy check against the brief: plain words, no "fraud"/"scam", every
   warning ends with a next step.
4. Write ui/SCREENS.md with one line per state and the fixture + step that
   shows it (Coco uses this for review and for the backup video).

Done when: Coco can play the S1 fixture end to end with nothing that looks
unfinished. List any remaining rough edges under Status rather than fixing
off-path screens.
```

### T9. Demo notes and backup video (UI-11)

```text
Task T9 (UI-11): ui/DEMO.md and the backup video (due Sun 09:00).

1. ui/DEMO.md: demo-machine steps (Ollama running, BlackHole route, Wi-Fi
   toggle location, window placement next to Zoom, how to start
   python -m callguard.server with and without --fake, how to open replay as
   the fallback), and the click-by-click demo path from ui-flows.md §5.
2. Script the backup recording: a fixture-driven run of S1 with Wi-Fi-off
   rerun. Coco records the screen on the Mac; the video file stays off-repo.

Done when: someone who has not seen the app can run the demo from DEMO.md.
```

### T10. Side buttons and firm rules panel (P1: UI-9, UI-13)

```text
Task T10 (UI-9, UI-13), only after the Sat 22:00 P0 checkpoint is green.

1. F10: at watch level, two quiet buttons under the watch note:
   "Check with a colleague" (sends colleague, toast as in T7) and
   "Mark as safe" (single click is fine outside danger; sends mark_safe).
2. F11: collapsible "Your firm's rules (N)" section from the rules message,
   each rule's text, with a "came up 1×" badge for rules in rules_broken this
   call. Badges reset on call started.

Done when: s1 shows the buttons at watch; s2 shows the bank rule with a badge.
```

### T11. Post-call summary card (P2: UI-10)

```text
Task T11 (UI-10), scoped out this weekend; build only if Coco asks.
On call ended, show a card: "<scenario guess from tactics> · N warning signs ·
you <hung up and called back | checked with a colleague | marked it safe>".
No transcript, no quotes. Dismiss clears it from memory.
```

---

## Part C. Review checklist for Coco (per UI PR)

- [ ] Only `ui/` and `tests/ui/` changed (plus a Status line in `ui/AGENTS.md`)
- [ ] Runs from replay with Wi-Fi off; no external URLs in `ui/` (`grep -r "http" ui/ | grep -v localhost`)
- [ ] No storage APIs; transcript cleared on call end
- [ ] Copy: plain words, no "fraud/scam", next step present
- [ ] Works without v2 fields (try a v1-only `check`)
- [ ] Screenshots at 360 px light/dark in the PR
- [ ] `pytest` green offline
