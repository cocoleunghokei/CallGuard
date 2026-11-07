# Callguard UI: user flows

Owner: Coco (Lead). Readers: the UI lane agent, and Coco when reviewing UI PRs.
Source of truth for requirements is [prd.md](prd.md) (§4 scenarios, §6.8 actions, §7 gate, §9 UX, §13.5 UI-1..13). This file turns those into **flows a user walks through**, screen by screen, with the WebSocket messages that drive each step. The task prompts that build them are in [ui-tasks.md](ui-tasks.md).

---

## 0. The person and the moment

**Maria, paralegal, 12-person firm.** Zoom is open full width on a 13" MacBook. Callguard is a narrow window (≈360 px) pinned to the right. She is on the call, half-listening to the caller, half-typing in another app. She will glance at Callguard for under a second at a time, so every state must be readable in one glance: **colour + icon + one word**.

What she needs, in order:
1. *Nothing*, while the call is normal. The panel must stay calm and quiet.
2. A **nudge** ("verify first") when the call starts to look like a script.
3. A **stop** with the safe way out in hand (the real number, a colleague) when the caller asks for the thing a scam is after.
4. **Proof** that her call is not being recorded or uploaded.

---

## 1. Screens and regions

```
Side panel (always on top, ~360 px wide)          Danger overlay (full window / full screen)
┌──────────────────────────────┐                  ┌──────────────────────────────────────────┐
│ ● Listening locally ·        │ A  header        │ ⚠ STOP AND VERIFY THIS CALL  Strong ■■■■■ │
│   nothing stored     ◌ Online│                  │ The caller claims to be: …               │
├──────────────────────────────┤                  │ • tactic   "caller's words"              │
│ [banner: Basic checks only]  │ B  banners       │ Firm rule: …                             │
├──────────────────────────────┤                  │ Real public number: … · source           │
│  ✓ LOW   No clear signs ■■□□ │ C  risk meter    │ 🔒 Typing paused … (1:54)                │
│  reason line + tactic chips  │ D  watch note    │ [Hang up and call back] [Check w/ coll.] │
├──────────────────────────────┤                  │ Type SAFE and hold: [____] (hold 3 s)    │
│ caller: …                    │ E  transcript    └──────────────────────────────────────────┘
│ you: …                       │    tail (3 lines)
├──────────────────────────────┤
│ What left this device (0)    │ F  egress log
│ Nothing has left this device │
├──────────────────────────────┤
│ [Check with a colleague]     │ G  actions (P1)
│ [Mark as safe]               │
└──────────────────────────────┘
```

Region letters are used in the flows below.

---

## 2. Message → UI cheat sheet

| Message (`type`) | Region | What changes |
|---|---|---|
| `status` | A, B | Listening badge, online dot, model banner, gate mode |
| `call` `started` | all | Leave Idle; clear tail, egress-this-call count, chips |
| `call` `ended` | all | Back to Idle; **wipe** transcript tail and current check from memory |
| `transcript` | E | Append; keep last 3 lines only |
| `check` | C, D, overlay | Meter level + bar; watch note; open overlay on `danger` |
| `verify` | D, overlay | Verify line: number + source, "Looking up…", "Offline, search skipped", "Couldn't find a public number, use the one on file" |
| `egress` | F | Prepend entry; flash the panel header once |
| `gate` | overlay | Lock line + countdown; exits enabled |
| `rules` | rules panel (P1) | List of firm rules |

UI → Server: `colleague`, `mark_safe`, `gate_release {how}`, `end_call`.

> v2 fields (`confidence`, `evidence`, `gate`, `call`, `rules`, `status.model`) come with LEAD-1. Until they land in `contracts.py`, the UI must **render without them** (no bar → show the level word only; no evidence → chips without quotes; no `gate` → overlay without the lock line).

---

## 3. Flows

Each flow lists: trigger, steps (what the user sees and does), the messages behind each step, and the acceptance check. Fixture names refer to `ui/dev/fixtures/*.json` (UI-8).

### F0. First open and consent
**Who/when:** Maria opens Callguard at the start of the day.
1. Panel opens in **Idle**: grey meter "Not on a call", badge "Listening locally · nothing stored", egress panel "Nothing has left this device".  ← `status {listening:false|true, online}`
2. A one-line consent note under the header: "Callguard checks this call on your laptop. Nothing is recorded or sent." with a small "Why?" disclosure (Massachusetts question, PRD Q2). Dismissible; stays dismissed for the session only.
3. If the Server is not reachable: banner "Callguard is starting…" and auto-reconnect every 2 s. No error dialogs.

**Done when:** `idle.json` renders exactly this; killing the WebSocket shows the reconnect banner and recovers without a reload.

### F1. A normal call stays quiet (benign twins B1, B2, B7)
1. Call starts. Meter goes green **✓ LOW · No clear signs**. ← `call started`, `check {risk:low}`
2. Transcript tail scrolls the last 3 lines, tagged `Caller` / `You`. ← `transcript`
3. B2 ("need this by five"): still low. B7 (Maria says "don't tell anyone, it's a surprise"): still low; nothing flashes.
4. Call ends: tail clears, meter back to grey Idle. Egress panel still says "Nothing has left this device". ← `call ended`

**Done when:** `b2_colleague.json` and `b7_you_say_it.json` replay with zero amber/red frames and no sound.
**Design intent:** this is most calls. If the panel twitches here, users learn to ignore it.

### F2. Watch: "verify first" nudge (S1 beat 2, B3, B6)
1. Caller: "You're under investigation…" Meter turns amber **◐ WATCH · Some signs ■■■■■■■□□□**. ← `check {risk:watch, confidence:0.71}`
2. Watch note (D): one line `reason`, then tactic chips in plain words: "Claims to be an official" · "Threatens you". ← `check.tactics`
3. Tapping a chip expands the caller's exact words: *"you're under investigation and could face extradition"*. ← `check.evidence[].quote`
4. If `rules_broken` is non-empty, the rule text shows here too ("Firm rule: …").
5. A verify line appears: "Checking Department of Justice's public number…" then the number. ← `verify`
6. If the next 3 checks are low, the meter decays back to green (Server-side smoothing; UI just follows `check`).

**Done when:** `s1_government.json` shows the amber state with 2 chips, each expandable to a quote; `b3_real_bank.json` peaks at watch at most, no overlay.
**No sound at watch.** Colour + icon + word only.

### F3. Danger: stop and verify (S1 beat 3, S2 beat 2, S3, S4)
1. Caller: "Do not tell your colleagues…" Meter turns red **⚠ DANGER · Strong signs**. ← `check {risk:danger}`
2. Overlay opens over the panel (full window; full screen if pywebview, SRV-11), one short sound, focus on **Hang up and call back**.
3. Overlay content, top to bottom (PRD §9.4):
   - Headline "Stop and verify this call" + bar
   - "The caller claims to be: Department of Justice"
   - Each tactic in plain words with its quote
   - "Firm rule: Agencies don't ask for bank details by phone." (one line per broken rule, rule text from `rules`/fixture)
   - "Real public number: (202) 514-2000 · source: justice.gov"
   - `next_step`
   - Exits (F5)
4. Danger is **sticky**: if the caller goes quiet, the overlay stays.

**Done when:** `s1_government.json`, `s2_vendor_bank.json`, `s3_it_code.json` each open the overlay with tactic + quote + rule (if any) + number/verify line + next step (PRD §3.3 "explains itself").

### F4. Keyboard gate locks (S1 beat 4, S2 beat 3, S3 beat 2, S4 beat 3)
1. Caller: "Read me your account number." ← `gate {state:locked, mode, reason, release_in:120}`
2. Overlay adds the lock line: "🔒 Typing is paused while this call asks for bank details (1:54)". Countdown ticks locally from `release_in`.
3. Maria tries to type in her bank tab: nothing (hard gate) or the overlay keeps focus (soft gate). Enter and Esc **do nothing** on the overlay.
4. At 0:00 the gate releases on its own (Server sends `gate {state:off}`); the overlay stays in danger mode, minus the lock line.

**Done when:** keyboard-only test: Tab reaches every exit, Enter/Esc never dismiss, countdown matches `release_in`.

### F5. Taking a safe exit (from F3/F4)
Three exits, ordered so the safe one is easiest:

| Exit | Effort | UI sends | Then |
|---|---|---|---|
| **Hang up and call back** (primary) | 1 click | `gate_release {how:"hang_up"}` | Big card with the verified number (or "Use the number on file") and "Copy number". Overlay closes when the call ends |
| **Check with a colleague** | 1 click | `colleague` + `gate_release {how:"colleague"}` | Toast "Heads-up sent. Stay on the line or hang up, your choice." |
| **I've verified, it's safe** | type `SAFE` + hold 3 s | `mark_safe` + `gate_release {how:"mark_safe"}` | Overlay closes, meter goes green, small "Marked safe" note |

- The hold button shows a 3 s fill; letting go resets it. `SAFE` is case-insensitive, visible as typed.
- After any release the gate only re-locks for a **new** ask tactic (Server rule; UI just obeys `gate`).

**Done when:** each exit sends exactly the listed messages (assert in replay harness log), and mark-safe is impossible with a single click or a single keypress.

### F6. Prove privacy: "What left this device" (demo beat, G3)
1. During S1 watch, one entry appears: `19:02:11 · api.tavily.com · "Department of Justice" · ok`. The F region header flashes once. ← `egress`
2. Clicking an entry shows exactly what was sent (the org name, nothing else) and a line "Your call audio and words never leave this laptop."
3. Count in the header: "What left this device (1)".
4. Normal calls: stays "Nothing has left this device". **The empty state is the feature**, so design it, don't apologise for it.

**Done when:** `s1_government.json` shows exactly one entry with the org name; `b1_vendor_invoice.json` shows the empty state.

### F7. Wi-Fi off mid-call (offline demo)
1. Maria turns Wi-Fi off. Dot turns grey "Offline". ← `status {online:false}`
2. Scam still gets caught: meter, chips, overlay all work.
3. Verify line: "Offline, search skipped. Use the number on file." ← `verify {status:"offline"}`
4. Egress log shows the attempt with status `offline` (it was recorded before the call). ← `egress {status:"offline"}`

**Done when:** `offline.json` replays the S1 sequence with these three differences and nothing else.

### F8. Local model down (degraded)
1. Banner (B) amber: "Basic checks only, local model unavailable". ← `status {model:"degraded"|"offline"}`
2. Meter still works but tops out at **watch** (phrase checks only, PRD G3). Chips show; quotes may be missing.
3. A `check` with `source:"fallback"` shows the reason line ("Couldn't run the full check") in grey, never as a warning.

**Done when:** `model_down.json` renders the banner and never opens the overlay.

### F9. Call ends: clear and (P2) summary
1. ← `call ended`: transcript tail, chips, quotes and current check are **deleted from memory** (not just hidden). Overlay closes.
2. Egress entries stay for the session (they contain only org names), grouped under "Earlier today".
3. P2 only: summary card "Possible government-impersonation scam · 3 warning signs · you called back." Dismiss clears it. No transcript.

**Done when:** after `call ended`, a DOM + JS-state check finds none of the call's transcript text (UI-7 test).

### F10. Colleague / safe outside danger (P1, UI-9)
At watch level, two quiet buttons under the note: "Check with a colleague" (sends `colleague`) and "Mark as safe" (single click is fine here because there is no gate; sends `mark_safe`, meter goes green).

### F11. Firm rules panel (P1, UI-13)
Collapsible "Your firm's rules (5)" section; each rule's text, with a red count badge "fired 1×" for rules broken this call. ← `rules`, `check.rules_broken`

---

## 4. Flow → scenario → fixture map

| Flow | Scenarios that exercise it | Fixture(s) (UI-8) | Priority |
|---|---|---|---|
| F0 First open | — | `idle.json` | P0 |
| F1 Normal call | B1, B2, B7 | `b1_vendor_invoice.json`, `b2_colleague.json`, `b7_you_say_it.json` | P0 |
| F2 Watch | S1 b2, B3, B6 | `s1_government.json`, `b3_real_bank.json` | P0 |
| F3 Danger | S1, S2, S3, S4 | `s1_…`, `s2_vendor_bank.json`, `s3_it_code.json`, `s4_partner_wire.json` | P0 |
| F4 Gate | S1 b4, S2 b3, S3 b2, S4 b3 | same as F3 | P0 |
| F5 Exits | any danger | same as F3 | P0 |
| F6 Egress | S1 (one org), B1 (none) | `s1_…`, `b1_…` | P0 |
| F7 Offline | S1 offline | `offline.json` | P0 |
| F8 Model down | S1 phrase-only | `model_down.json` | P0 |
| F9 Call end | all | every fixture ends with `call ended` | P0 (summary P2) |
| F10 Side buttons | S1 b2 | `s1_…` | P1 |
| F11 Rules panel | S2 | `s2_…` | P1 |

---

## 5. Demo path (what judges see, 3 min)

F0 (badge, empty egress) → F1 for a few seconds (Gradium "David" opener, panel stays calm) → F2 on "under investigation" → F6 entry appears → F3 on "don't tell your colleagues" → F4 when asked for bank details, presenter tries to type → F5 "Hang up and call back" with the real number → **Wi-Fi off**, rerun to F7 → F9 call end, panel wipes.

Every screen in that path must look finished. Anything off the path can be plain.
