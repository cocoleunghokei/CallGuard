# HACK1984: Project plan

Product: **Callguard** (working name). See [background.md](background.md) for the why.
Hacking: **Sat 11:00 → Sun 11:00 (code freeze)**. Judging Sun 12:00.

---

## 1. What we ship

### P0: must work for the demo
- [ ] Capture call audio on the Mac (caller via BlackHole, you via mic)
- [ ] Live local transcription (faster-whisper), English
- [ ] Local scam check (Ollama + Qwen 2.5 7B, or 3B if slow), returning risk level, tactic and reason
- [ ] Firm rules check (3–5 rules from a JSON file)
- [ ] Warning screen: risk meter, plain-language reason; on danger a notification and sound, and clicking it opens the danger warning with the safe next step (never freezes the keyboard)
- [ ] "What left this device" log
- [ ] Works with the Wi-Fi off (except the search step, which says "offline, skipped")

### P1: makes it win
- [ ] Surge: search the claimed company or agency name with Tavily or Exa and show its real public number (P1: also show recent impersonation-scam reports for that name). The name is checked first so the search never exposes the user or the firm
- [ ] "Check with a colleague" button (sends a message to one preset contact; a local notification is fine for the demo)
- [ ] Mandarin support (Whisper detects the language, and Qwen handles Chinese)
- [ ] Gradium-cloned "managing partner" voice clip for the demo opener (pre-recorded)
- [ ] iPhone calls answered on the Mac, **only if the Continuity test passes**

### P2: only if ahead by Sat 22:00
- [ ] Training mode: a Gradium voice plays a scam call, and the app scores the response
- [ ] Admin view with anonymous alert counts
- [ ] Phonon coach line in AirPods

### Out of scope
iPhone app, Android app, browser extension, saving audio or transcripts.

---

## 2. Tech stack

| Part | Choice | Why |
|---|---|---|
| Audio capture | BlackHole 2ch + Multi-Output Device, read with `sounddevice` | Fastest working route on a Mac |
| Speech-to-text | `faster-whisper` (`small`, int8) | Local, fast enough, handles Mandarin |
| Scam check | Ollama + `qwen2.5:7b` (fallback `qwen2.5:3b`) | Local, good in English and Chinese, returns JSON |
| Backend | Python + FastAPI + WebSocket | One process, pushes alerts to the screen |
| Screen | Simple local web page (`localhost`), kept on top next to Zoom | Easiest to build and style |
| Search | Tavily or Exa API | Surge track |
| Demo voice | Gradium Voice Cloning (cloud, pre-recorded) | Demo content only, no user data |

**How it fits together**
```
Call audio ──BlackHole──▶ capture.py ──3s chunks──▶ faster-whisper ──text──▶
rolling 30s transcript ──▶ Ollama scam check + rules check ──JSON──▶
FastAPI WebSocket ──▶ warning screen
                    └─▶ (claimed org only) Tavily/Exa ──▶ real number
```

**Scam check output (the model must return this JSON)**
```json
{
  "risk": "low | watch | danger",
  "tactics": ["authority", "secrecy", "urgency", "threat", "credential_request", "bank_change", "bypass_approval"],
  "claimed_identity": "Boston Police / Chase / IT support / null",
  "rules_broken": ["no_bank_changes_by_phone"],
  "reason": "Caller claims to be a government official and asked you not to tell colleagues.",
  "next_step": "Hang up and call the agency's public number."
}
```

---

## 3. Team and roles (up to 4)

| Role | Owns | Person |
|---|---|---|
| **Lead / product** | Scope, the model prompt and rules, demo script, pitch, talking to the friend and sponsors | Coco |
| **Audio + transcription** | BlackHole setup, `capture.py`, faster-whisper chunking, Continuity test | |
| **Model + backend** | Ollama prompt, JSON parsing, rules check, FastAPI, Tavily/Exa | |
| **Screen + demo** | Warning screen, danger notification and warning, "what left" log, backup video | |

Solo or 3 people: merge Model + backend with Lead.

---

## 4. Timeline

### Saturday
| Time | Goal | Done when |
|---|---|---|
| 12:30–13:30 | **Continuity test** (section 5) and audio setup on the demo Mac | `caller.wav` has the caller's voice |
| 12:30–13:30 | Scam check prompt v1, tested on 6 written scripts (3 scams, 3 normal calls) | Correct risk on at least 5 of 6 |
| 13:00–13:45 | Sponsor fair: ask Gradium about cloning and Phonon, get Tavily/Exa keys, **ask the organizers about pre-existing code** | Keys in hand |
| 13:30–16:00 | Live transcription loop: 3s chunks in, text out | Words appear within ~3s of being spoken |
| 13:30–16:00 | Backend + WebSocket, warning screen v1 | Screen updates from a fake transcript |
| 16:00–19:00 | **Wire it together**: call → transcript → check → screen | First full run on a Zoom call |
| 19:00 | Dinner. Check-in: what's broken? | |
| 19:30–22:00 | Rules check, danger notification and warning, "what left" log, Wi-Fi-off run | P0 complete |
| 22:00 | **Decision point:** if P0 works, start P1. If not, fix P0 only | |
| 22:00–02:00 | P1: Surge lookup, check with a colleague, Mandarin, Continuity (if the test passed) | |

### Sunday
| Time | Goal |
|---|---|
| 02:00–07:00 | Sleep in shifts. One person tunes the prompt on more scripts |
| 07:00–09:00 | Polish the screen. Record the Gradium opener. **Record the backup demo video** |
| 09:00–10:30 | Rehearse the pitch 3 times, with a timer. Prepare Q&A answers |
| **11:00** | **Code freeze** |
| 12:00 | Judging |

---

## 5. Continuity test: can the Mac hear an iPhone call?

**Goal:** find out whether an iPhone call **answered on the Mac** can be captured. Run it first, Sat 12:30. Owner: Audio.
**Script:** [continuity-audio-test/test_capture.py](continuity-audio-test/test_capture.py)
**You need:** your Mac, your iPhone, a teammate's phone to call you, about 15 minutes.

### Step 1: turn on Continuity calls
- **iPhone:** Settings → Phone → Calls on Other Devices → On, and allow your Mac
- **Mac:** FaceTime → Settings → turn on **Calls from iPhone**
- Same Apple ID on both, Wi-Fi and Bluetooth on, both devices close together
- Check: a teammate calls your iPhone, and it should ring on the Mac too

### Step 2: install BlackHole and the packages
```bash
brew install blackhole-2ch
pip3 install sounddevice soundfile numpy faster-whisper
```
Restart the Mac if BlackHole doesn't appear in Audio MIDI Setup.

### Step 3: send the Mac's sound to BlackHole and the speakers
1. Open **Audio MIDI Setup** (Spotlight: "Audio MIDI")
2. Click **+** at the bottom left → **Create Multi-Output Device**
3. Tick **MacBook Pro Speakers** and **BlackHole 2ch**
4. **System Settings → Sound → Output → Multi-Output Device**
5. Use the Mac's speakers, **not AirPods**, for this test (Bluetooth makes multi-output flaky)

### Step 4: run the test
```bash
cd ~/Desktop/Hack1984/continuity-audio-test
python3 test_capture.py 30
```
1. Once it says "Start the call now," have the teammate call your iPhone
2. **Answer on the Mac** (the notification on the Mac's screen)
3. Teammate says: *"Hi, this is Officer Chen from the Department of Justice. You're under investigation. Don't tell your teammates."*
4. You reply: *"Who is this? Can I call you back?"*
5. Wait for the 30 seconds to finish

### Step 5: read the result
| Output | Meaning | Next |
|---|---|---|
| `caller.wav HEARD SOUND` and the teammate's words in the transcript | ✅ **Continuity works** | Add it to P1 and say "iPhone calls answered on your Mac" in the pitch |
| `caller.wav SILENT` | ❌ macOS isn't sending call audio through the normal output | Check that the output is still Multi-Output **during** the call (FaceTime can switch it). Retry once, then drop Continuity |
| `you.wav SILENT` | The mic is blocked while the call uses it | Try the mic as the call's input in FaceTime → Video → Microphone. Not a blocker, since the caller's side matters most |
| Both silent | Script or permission issue | System Settings → Privacy & Security → Microphone → allow Terminal |

### Step 6: repeat with the backup routes (5 min each)
- **Zoom call:** teammate calls you on Zoom, answer on the Mac, run the same script. **This must pass**, since it's the main platform
- **Speakerphone:** answer on the iPhone, on speaker, next to the laptop, and set the script's mic to the Mac mic. Shows the fallback works
- **AirPods:** add AirPods to the Multi-Output Device and repeat the Zoom test

Write the results here:

| Route | Caller heard? | You heard? | Transcript OK? | Notes |
|---|---|---|---|---|
| Continuity (Mac speakers) | | | | |
| Zoom (Mac speakers) | | | | |
| Speakerphone next to laptop | | | | |
| Zoom with AirPods | | | | |

---

## 6. Test scripts for the scam check

Write these out and use them for prompt tuning and the demo.

| # | Script | Expected |
|---|---|---|
| 1 | Fake government official: under investigation, don't tell colleagues, verify bank details (the friend's case) | danger: authority, secrecy, threat, bank request |
| 2 | Fake vendor: new bank account, update before Friday's payment | danger: bank_change + rule broken |
| 3 | Fake IT: read me the code we just texted you | danger: credential_request |
| 4 | Real vendor: invoice question, no money moves | low |
| 5 | Real colleague: schedule a meeting, mentions a deadline | low (urgency alone isn't a scam) |
| 6 | Real bank: confirms a recent charge, asks you to call the number on your card | low or watch |
| 7 | Script 1 in Mandarin | danger |

---

## 7. Demo script (3 minutes)

| Time | Beat |
|---|---|
| 0:00–0:20 | **Hook:** play the Gradium-cloned "managing partner" voice: "Hey, it's David, I need you to wire the escrow funds before 5." "You couldn't tell that was fake. Neither could my friend." |
| 0:20–0:50 | **Story + problem:** the friend's call. Phone scams succeed 40% more often than phishing emails. Today's tools check the number, not what's said |
| 0:50–2:00 | **Live demo:** teammate calls on Zoom as the "official" (script 1). The risk meter rises, then the danger notification appears at "don't tell your teammates." Click it: the warning shows the tactic, the caller's words and the real agency number from search |
| 2:00–2:20 | **Privacy proof:** Wi-Fi off, run script 2, still caught. Show the "what left this device" log |
| 2:20–2:45 | **Business:** firms of 10–200, $10–20 per seat, one stopped wire pays for years. Why us |
| 2:45–3:00 | **Close:** "You can't tell the voice. You can tell the script." |

**Prepared answers**
- *"She was on her mobile, how does this help?"* Phones block apps from hearing calls. We cover work calls and iPhone calls answered on the Mac, and "check with a colleague" works on any call.
- *"Isn't recording calls illegal in Massachusetts?"* We store nothing and show a notice. (Confirm with the friend first.)
- *"What about Microsoft?"* Teams only, needs a security team. We cover every calling app for firms without one.
- *"False alarms?"* We say "verify first," never "this is fraud," and real calls stayed low in our tests.

---

## 8. Checkpoints

- [ ] **Sat 13:30:** Continuity test done, and the Zoom route works
- [ ] **Sat 19:00:** first full run, call to screen
- [ ] **Sat 22:00:** P0 complete, Wi-Fi-off run works
- [ ] **Sun 02:00:** P1 features in or cut
- [ ] **Sun 09:00:** backup video recorded
- [ ] **Sun 10:30:** pitch rehearsed 3 times
- [ ] **Sun 11:00:** code freeze
