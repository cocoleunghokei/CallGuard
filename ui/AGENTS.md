# Lane: UI + demo

Read the root [AGENTS.md](../AGENTS.md) first. You own `ui/` and `tests/ui/` only.

## Delivers
A local web page (`ui/index.html` plus plain JS and CSS, no build step) served by the Server. It sits in a narrow window next to Zoom and reacts to the WebSocket messages in root AGENTS.md section 3.

## Tasks
Full flows and copy-paste task prompts (T1–T11, design brief): [hack1984/ui-flows.md](../hack1984/ui-flows.md), [hack1984/ui-tasks.md](../hack1984/ui-tasks.md). Work them in order.

**P0**
- [ ] "Listening locally" badge, and an online/offline indicator from `status`
- [ ] Risk meter: low / watch / danger
- [ ] "Watch" note: one line with `reason`
- [ ] "Danger" full-screen warning: tactic, rule broken, real number (from `verify`), `next_step`
- [ ] "What left this device" panel listing every `egress` message (empty is the point)
- [ ] Until the Server is ready, test with a fake WebSocket or a local JSON replay

**P1**
- [ ] "Check with a colleague" and "Mark as safe" buttons
- [ ] Post-call summary card

**Demo (owner of the backup)**
- [ ] Record the backup video of the full demo by **Sun 09:00**
- [ ] Keep the demo machine's setup steps in `ui/DEMO.md`

## Rules for this lane
- Plain words that a paralegal understands. Say "verify first," not "fraud"
- Never show or keep more transcript than the current call needs
- No external fonts, CDNs or analytics. The page must work with the Wi-Fi off

## Status
- [Sat 21:50] Done: visual prototype `ui/dev/prototype.html` (7 states, light + dark) for sign-off; T1 in progress (fixtures in `ui/dev/fixtures/`, `ui/ws.js`; replay.html and tests not yet written) | Next: finish T1 after Coco signs off on the look | Needs: `pytest` pinned in requirements.txt (Coco); rules.json text for S1's "bank details" ask (no bank-details tactic yet; fixtures use personal_data_request) (Detection)
