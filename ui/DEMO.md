# Callguard demo: machine setup and click-by-click path

For whoever runs the demo or records the backup video. Someone who has never seen the app should be able to follow this top to bottom.
Screens and the fixture step that shows each one: [SCREENS.md](SCREENS.md). Flows: [hack1984/ui-flows.md](../hack1984/ui-flows.md) §5.

## 1. One-time setup (demo Mac)

1. Python 3.11+ and a fresh venv in the repo root:
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Local model: install Ollama, then `ollama pull qwen2.5:7b` (slow laptop: `qwen2.5:3b` and `CALLGUARD_MODEL=qwen2.5:3b` in `.env`).
3. Whisper model, downloaded once while online (the app never downloads anything):
   ```bash
   python -c "from huggingface_hub import snapshot_download; print(snapshot_download('Systran/faster-whisper-small'))"
   ```
   Put the printed folder in `.env` as `CALLGUARD_WHISPER_DIR=…`.
4. Audio route: install BlackHole 2ch. In Audio MIDI Setup make a **Multi-Output Device** = your speakers/headphones + BlackHole 2ch, and set Zoom's speaker to it (you still hear the caller; Callguard hears them through BlackHole). Your mic stays your normal mic. Device names differ? set `CALLGUARD_CALLER_DEVICE` / `CALLGUARD_MIC_DEVICE` in `.env`.
5. `.env` (never committed): `TAVILY_API_KEY=…` (optional `EXA_API_KEY=…`), plus the two lines above.
6. Check it all:
   ```bash
   python -m callguard.audio.health     # "Audio inputs are ready."
   ollama list                          # qwen2.5 is there
   pytest                               # green, offline
   ```

## 2. Before going on stage

- Ollama running (`ollama serve` or the menu-bar app). Warm the model once: `ollama run qwen2.5:7b "hi"`.
- Wi-Fi **on** to start. The Wi-Fi toggle is in Control Center (top-right menu bar); have it one click away.
- Do Not Disturb **off** (the danger notification has to show), but quit Slack/Mail so nothing else pops up.
- Start the app:
  ```bash
  python -m callguard.server                 # live: listens to the Zoom call
  ```
  The Callguard window opens on top (400 × 760). Put it at the right edge of the screen, Zoom on the left.
- Check the header: just "Listening" ("Offline" appears next to it only with the Wi-Fi off). No yellow banner. If Ollama isn't answering there is no banner, so check it first (`ollama list`); watch reasons will say "Basic checks only". An audio banner means the mic or BlackHole isn't heard.

**No caller available / audio trouble?** Play a scripted call through the real pipeline instead (same window, same model, no mic):
```bash
python -m callguard.server --fake tests/detection/scripts/s1_government.txt
```
It starts as soon as the window connects. `--fake-speed 2` plays twice as fast.

**Model or laptop trouble?** The replay harness needs nothing but a browser (no Server, no Ollama, no network):
```bash
cd ui && python3 -m http.server 8080
```
Open `http://localhost:8080/dev/replay.html?f=s1_government&autoplay=1&speed=1`.

## 3. The demo path (3 min, ui-flows.md §5)

| # | Say / do | Callguard shows |
|---|---|---|
| 1 | Show the window before the call. Click the footer "Nothing sent online" | Grey "Not on a call"; the empty "Sent online (0)" panel ("Your call stays on this laptop"). Click it again to close |
| 2 | Caller ("David from the Department of Justice") opens politely | Call starts, green "Low · No clear signs", last 3 lines under "Latest" |
| 3 | Caller: "…your firm is under investigation…" | Amber "Watch": the reason, "Claims authority" / "Threatens you" pills (click one: the exact words), a "Say this" line, "Checking Department of Justice's public number…" |
| 4 | Point at the footer | It flashes once: `1 search sent: "Department of Justice"`. Click it: that name is the **only** thing sent, to api.tavily.com |
| 5 | Caller: "…don't tell your colleagues…" | Red warning fills the window, one short tone, the Mac notification (fixed text, no caller words). Tactics with their quotes, the firm rule, the real public number |
| 6 | Caller asks for bank details; presenter tries to type (it still works: nothing is blocked) | "This call is asking for bank details. Verify before you send anything…", "🔒 Pause ends in 2:00" counting down. Callguard keeps focus |
| 7 | Click **Report scam** | Toast "Heads-up for IT and your manager" with the fixed message and "Demo: not sent…"; the real public number stays on the warning |
| 8 | Hang up in Zoom, click **End call** (or wait 45 s of silence) | Panel wipes: no lines, no quotes left on screen or in memory |
| 9 | **Wi-Fi off**, run the call again | Header "Offline". Everything works the same, the lookup says "Offline, search skipped. Use the number on file." and the egress entry reads "Offline, not sent" |

The other exit, if asked: **Type SAFE + hold 3 s** (meter back to green, "Marked safe").

## 4. Backup video (due Sun 09:00, file stays off-repo)

1. Wi-Fi on. `python -m callguard.server --fake tests/detection/scripts/s1_government.txt`
2. QuickTime → New Screen Recording, select the Callguard window plus a little of the desktop. Start, then let the replay play steps 1–8 above (click the egress footer at step 4, Report scam at step 7).
3. Wi-Fi off, restart the same command, record step 9.
4. Save outside the repo.
