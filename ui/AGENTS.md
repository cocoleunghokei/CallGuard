# Lane: UI + demo

Read the root [AGENTS.md](../AGENTS.md) first. You own `ui/` and `tests/ui/` only.

## Delivers
A local web page (`ui/index.html` plus plain JS and CSS, no build step) served by the Server. It sits in a narrow window next to Zoom and reacts to the WebSocket messages in root AGENTS.md section 3.

## Tasks
Full list with IDs and "done when": [prd.md §13.5](../hack1984/prd.md#135-ui--ui-testsui).

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
- (none yet)
