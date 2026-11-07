# Callguard screens: where to see each state

For review and for the backup video. Serve `ui/` and open the replay harness (no Server, no Ollama, no network):

```bash
cd ui && python3 -m http.server 8080
```

Then open `http://localhost:8080/dev/replay.html?f=<fixture>&autoplay=0` and press **Step** until the harness counter (top right of the "Server → UI" log) shows the step below. `&autoplay=1&speed=1` plays the fixture in real time instead.
"Step N" means N messages delivered. Times are the fixture's `at` seconds.

## Demo path (ui-flows.md §5), fixture `s1_government`

| # | State | Step (time) | What to look for |
|---|---|---|---|
| 1 | Idle, F0 | 2 (0.5 s) | Grey ○ "Not on a call", "Listening locally · nothing stored", "Online · Safe pause on", consent line, "Nothing has left this device" |
| 2 | Call started, low, F1 | 3–7 (1.0–12 s) | Green ✓ "Low · No clear signs" + 3/10 bar, "Latest" shows the last 3 lines, "End call" in the footer |
| 3 | Watch, F2 | 8 (15.0 s) | Amber ◐ "Watch · Some signs" 7/10, Why: reason + "Claims authority", "Threatens you" (click to see the quote), Say line, "Checking Department of Justice's public number…", next step |
| 4 | Egress entry, F6 | 9 (16.0 s) | Footer flashes once, "1 item left: "Department of Justice"". Click it: panel "What left this device (1)", entry 19:02:11 · api.tavily.com · Sent |
| 5 | Verified number | 10 (17.4 s) | "Public number · justice.gov (202) 514-2000" with Copy |
| 6 | Danger, F3 | 13 (25.9 s) | Warning opens over the panel with one tone, focus on "Hang up and call back": claimed identity, 3 signs with quotes, firm rule, "Real public number…", Say, next step, egress line at the foot |
| 7 | New sign, updated in place | 15 (32.9 s) | 4th sign "Asks for client or personal data" + second firm rule, no second tone |
| 8 | Pause, F4 | 16 (33.6 s) | Red top adds "This call is asking for bank details…", "🔒 Pause ends in 2:00" counting down, "Callguard is keeping focus…". Enter and Esc do nothing |
| 9a | Exit: Hang up and call back, F5 | at step 16, press Space or click | "Hang up now", "(202) 514-2000 · Department of Justice · justice.gov", "Copy number". UI → Server log: `gate_release how="hang_up"` |
| 9b | Exit: Check with a colleague | at step 16, click | Toast "Heads-up for IT and your manager", the fixed message, "Demo: not sent…"; nothing added to "What left this device". Log: `colleague`, `gate_release how="colleague"` |
| 9c | Exit: it's safe | at step 16, type SAFE, hold "Hold 3 s" | Warning closes, "Low · Marked safe". Log: `mark_safe`, `gate_release how="mark_safe"` |
| 10 | Pause runs out (no exit taken) | 17 (48.6 s) | Back to the red panel "Danger", "Show the warning" button reopens it (no tone) |
| 11 | Call ended, F9 | 18 (49.1 s) | Grey idle again, no transcript anywhere; the egress entry stays under "Earlier today" |

## Wi-Fi off, fixture `offline` (F7)

| State | Step (time) | What to look for |
|---|---|---|
| Offline header | 1 (0 s) | Grey dot, "Offline" in bold |
| Lookup skipped | 9–10 (16.0–16.1 s) | Footer stays "Nothing has left this device · 1 skipped"; entry shows "Offline, not sent"; verify line "Offline, search skipped. Use the number on file." |
| Still caught | 13–16 | Same warning and pause as S1, verify line offline |

## Other states

| State | Fixture | Step | What to look for |
|---|---|---|---|
| Local model down, F8 | `model_down` | 1 → end | Banner "Basic checks only, local model unavailable"; tops out at Watch, never opens the warning |
| Normal call stays calm | `b1_vendor_invoice` | 1 → end | Low the whole call, "Nothing has left this device" |
| Bank change, no public number | `s2_vendor_bank` | 8, 10 | Warning with "Firm rule: We never change vendor or client bank details…", "Couldn't find a public number, use the one on file." |
| Code request | `s3_it_code` | 8, then wait 5 s | "Checking…" line, hidden after 5 s with no lookup answer |
| Partner wire | `s4_partner_wire` | 8, 10 | "Asks you to send money", "Wants you to skip the usual approval", two-approvals rule |
| Connecting | any | press "Drop connection" | Banner "Connecting to Callguard…", recovers in 2 s |
| Wide window | `s1_government` | 13 | Window > 700 px: the panel stays 560 px wide and centred; the warning is a centred 720 px card |
