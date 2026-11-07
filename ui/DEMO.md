# Callguard demo: machine setup, stage run, backup video

For whoever runs the demo, including someone who has never seen the app. Every state is listed with the exact step that shows it in [SCREENS.md](SCREENS.md). Pitch timing is in [project-plan.md §7](../hack1984/project-plan.md#7-demo-script-3-minutes).

> **Status (Sun 04:40).** These two routes are ready: **B (scripted call in the real app)** and **C (replay in a browser, no Server)**. **A (live Zoom call)** still needs the Audio lane's `capture.py` (AUD-2), which isn't merged yet. There is also no `requirements.txt` yet (LEAD-3), and the native window has not been tried on a Mac (see the SRV-11 note). Update this box when they land.

---

## 1. One-time setup on the demo Mac

1. **Python 3.11+** and the repo:
   ```bash
   git clone https://github.com/cocoleunghokei/scam-call-detecter.git && cd scam-call-detecter
   ```
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   ```
   ```bash
   pip install -r requirements.txt
   ```
   If `requirements.txt` isn't there yet, install what the lanes listed under **Needs**: `fastapi`, `uvicorn[standard]`, `httpx`, `python-dotenv`, `pywebview`, `pyobjc-framework-Cocoa`, `pytest`, plus the Audio lane's packages (`sounddevice`, `numpy`, `faster-whisper`) for route A.
2. **Local model.** Install Ollama, then:
   ```bash
   ollama pull qwen2.5:7b
   ```
   Fallback model: `qwen2.5:3b` (set `CALLGUARD_MODEL=qwen2.5:3b`). It runs on `localhost`, so it keeps working with the Wi-Fi off.
3. **Search key.** Create `.env` at the repo root (git ignores it): `TAVILY_API_KEY=…`. Optional: `CALLGUARD_NEVER_SEARCH=Firm name,Client name` (names never sent to search).
4. **Call audio (route A only).** Install **BlackHole 2ch**. In *Audio MIDI Setup*, create a **Multi-Output Device** with BlackHole 2ch + your headphones. In Zoom, set **Speaker** to that Multi-Output Device and **Microphone** to the built-in mic. Callguard reads the caller from BlackHole and you from the mic. Override the device names with `CALLGUARD_CALLER_DEVICE` / `CALLGUARD_MIC_DEVICE` if needed.
5. **Notifications.** Callguard's danger notification is posted by the app through macOS (`osascript`). Run route B once and allow the notification when macOS asks. If none appears, check *System Settings → Notifications* for the entry that posted it (usually "Script Editor") and allow banners + sound.
6. **Rehearse offline without touching Wi-Fi:** prefix any run with `CALLGUARD_OFFLINE=1` to force "Offline".

## 2. Fifteen minutes before going on stage

- [ ] Ollama is running (`ollama list` answers).
- [ ] Wi-Fi **on**. You know where the toggle is: the Wi-Fi icon in the menu bar (or Control Centre). Practise turning it off with one click.
- [ ] **Do Not Disturb / Focus off**, or the danger notification won't show.
- [ ] Volume up: the warning plays one short tone.
- [ ] Close everything else. Zoom on the left, the Callguard window (400 × 760, always on top) against the right edge of the screen. On a 13" display, leave Zoom at least 900 px wide.
- [ ] Dismiss the consent line once ("Checks run on this laptop…" ×) only if you're short on space. It's a good line to read out, though.
- [ ] Backup video open in QuickTime, paused on the first frame, on a second desktop (Ctrl → to switch).

## 3. Three ways to run it (most real first)

**A. Live Zoom call** (needs AUD-2):
```bash
python -m callguard.server
```
The Callguard window opens on top. A teammate calls you on Zoom and reads S1 from [prd.md §4.2](../hack1984/prd.md) (the "Department of Justice" script).

**B. Scripted call in the real app** (no second person, no audio). The Server plays the script into the real pipeline and model:
```bash
python -m callguard.server --fake tests/detection/scripts/s1_government.txt
```
The call starts when the window connects. To replay (for example after turning Wi-Fi off), close the window and run the command again. `--fake-speed 2` plays twice as fast.

**C. Fallback: replay in a browser** (no Server, no Ollama, no network, nothing to fail):
```bash
cd ui && python3 -m http.server 8080
```
Then open `http://localhost:8080/dev/replay.html?clean=1&f=s1_government,offline` in Safari or Chrome, and narrow the browser window to sit next to Zoom. A browser tab can't stay always-on-top. Without `clean=1` you get the dev controls (Step, speed, message logs).

## 4. The demo path, click by click (≈ 70 s of the 3 min)

| Pitch time | You do / say | Callguard shows |
|---|---|---|
| 0:50 | Point at the window: "Listening locally, nothing stored. Nothing has left this device." | Grey ○ "Not on a call", green "Listening locally · nothing stored", footer "Nothing has left this device" |
| 0:55 | Call starts (A: answer Zoom · B: run the command) | Green ✓ "Low · No clear signs", last three lines under "Latest" |
| ~1:10 | Caller: "…you're under investigation…" | Amber ◐ "Watch · Some signs", pills "Claims authority", "Threatens you" (click one: the caller's exact words), Say line |
| ~1:12 | "The only thing that leaves the laptop is the name they claimed." Click the footer | Footer flashes: `1 item left: "Department of Justice"`. Panel: 19:02:11 · api.tavily.com · "Department of Justice" · Sent |
| ~1:20 | Caller: "…do not tell your colleagues…" | Mac notification "Callguard: verify this call before you act" + one tone. The red warning opens over the panel: claimed identity, each sign with the caller's words, firm rule, "Real public number: (202) 514-2000 · source: justice.gov" |
| ~1:30 | Caller asks for bank details. Try typing in Zoom chat: it still works, and Callguard only keeps focus | "This call is asking for bank details…", "🔒 Pause ends in 2:00" counting down. Enter and Esc do nothing |
| ~1:40 | Click **Hang up and call back** | "Hang up now", the real number big, "Copy number" |
| 1:50 | Call ends | Panel wipes back to grey. No transcript anywhere |
| 2:00 | **Turn Wi-Fi off.** Rerun (B: close the window and run the command again) | Header "Offline". Same call is still caught; verify line "Offline, search skipped. Use the number on file."; footer "Nothing has left this device · 1 skipped" |
| 2:15 | Click the footer: "Even the name didn't go out." | Entry "Offline, not sent" |

Other exits, if a judge asks: **Check with a colleague** (toast "Heads-up sent…") and **Verified it's safe?** (type SAFE, then hold the button for 3 s; a single click never does it).

## 5. If something breaks on stage

| Symptom | Do this |
|---|---|
| Window shows "Connecting to Callguard…" | The Server isn't running. Rerun the command. It reconnects every 2 s by itself |
| Banner "Basic checks only, local model unavailable" | Ollama is down. Carry on: phrase checks still reach Watch. Or switch to the backup video |
| No notification at danger | Focus mode is on. Carry on, the warning in the window is the real thing |
| Live audio silent (route A) | Switch to route B with the same script. Say "here's the same call, scripted" |
| Anything else | Ctrl → to the backup video desktop and press Space |

## 6. Recording the backup video (UI-11, due Sun 09:00)

The video file stays **off the repo** (put it in the team drive).

1. Route C server: `cd ui && python3 -m http.server 8080`.
2. In Chrome or Safari, open:
   ```
   http://localhost:8080/dev/replay.html?clean=1&f=s1_government,offline&exit=hang_up
   ```
   This plays S1 in real time. "Hang up and call back" is clicked by itself 4 s after the pause locks. Then a title card "Wi-Fi off. Same call again." appears and the offline run plays (≈ 1 min 45 s in all, hands-free).
   - `exit=` leave it out to click the exits yourself; `exit=colleague` shows the other exit.
   - `exit_after=6` waits longer before the click; `gap=6` holds the title card longer.
   - `autoplay=0` waits for you to press Play (the controls are hidden in clean mode, so leave `autoplay` out for recording).
3. Record with QuickTime (*File → New Screen Recording*, record a selected area around the window), or ⇧⌘5.
4. **Sound:** QuickTime doesn't record system audio on its own. To capture the warning tone, pick BlackHole as the recording input with the Multi-Output Device as the system output, or add the tone in editing.
5. Before you cut: check the take shows the footer flash, the warning tone moment, the countdown and the call-back number. Record one light-mode and one dark-mode take (*System Settings → Appearance*), and keep the better one.
6. Optionally put the Gradium "David" voice clip (LEAD-9) at the start in editing.
