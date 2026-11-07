# HACK1984: Background

Working product name: **Callguard** (placeholder, rename freely)
Last updated: Sat Nov 7, 2026

---

## 1. The hackathon

**HACK1984**, Sat Nov 7 – Sun Nov 8, 2026, 300 Massachusetts Ave, Boston.
Tagline: "Every tool you opened today is watching you. Spend a weekend building the ones that don't."
Run by Northeastern's Claude Builders Club, Rev, ACM and AINU. About 100 builders.

**Key times (Eastern)**

| When | What |
|---|---|
| Sat 11:00 | Hacking starts |
| Sat 13:00 | Sponsor and club fair (talk to Gradium, Tavily, Exa here) |
| Sat 14:00–17:00 | Workshops |
| Sun 10:30 | Judges check in |
| **Sun 11:00** | **Hacking ends. Code freeze** |
| Sun 12:00 | Judging |
| Sun 15:00 | Closing ceremony |

**Rules we know:** teams of up to 4. The page says nothing about pre-existing code, submission format or demo length. **Ask an organizer.**

Source: https://claudeneu.com/hackathon/

---

## 2. Tracks and judging criteria

| Track | What it asks for | Judged on | Prize |
|---|---|---|---|
| **Privacy-First** (main) | "Software that protects its users by design": local AI, anonymization, healthcare, local-first, encrypted, or collecting less data | What leaves the device, who can read it, whether you can prove it, whether anyone would use it | 1st: cash + 2-yr CodeCrafters VIP. 2nd: 1-yr. 3rd: 6-month. More to be announced |
| **Most Startup-able** (one prize) | The idea most likely to become a company. Sponsored by Misneach and FuzionX | Who it's for, whether they'd pay, why this team should build it | Cash |
| **Surge** (Tavily / Exa) | Build with Tavily's and/or Exa's search APIs | How central the API is, how well it works | Cash + CodeCrafters VIP, 3 places |
| Signal-to-Dose (Within3) | Lung cancer drug signal pipeline on a self-hosted model | Hidden-set accuracy, citations, trends, network-off run | TBA. **Not entering** |

**Gradium** is a Silver sponsor with no track or prize. Using it is for sponsor goodwill and demo impact, not scoring.

---

## 3. Prizes we're aiming for

1. **Privacy-First** (main goal): the product is built around "nothing leaves the laptop"
2. **Most Startup-able**: a clear B2B buyer who already loses money to this problem
3. **Surge** (secondary): search checks the caller's claimed identity

---

## 4. Winning strategy

1. **Prove the privacy claim live.** Turn the Wi-Fi off mid-demo and show the app still catches the scam. Show a "what left this device" log that's empty except for a company name sent to search.
2. **Lead with a real story.** A lawyer friend was scammed by a fake "government official" and gave up her bank details. Every warning sign was in the words, not the voice.
3. **"You can't tell the voice. You can tell the script."** AI voices keep improving, but scam scripts stay the same. Open with a Gradium-cloned voice to show the voice can't be trusted.
4. **One buyer, one platform.** Small professional firms on their laptops. No phone workarounds.
5. **Be honest about limits.** Phones block apps from hearing calls. Say so before the judges ask, and show the "check with a colleague" button as the answer for mobile.
6. **A demo that can't fail.** Pre-record a backup video of the full flow by Sunday 9:00.

---

## 5. Product

**One line:** a desktop app that listens to work calls, spots scam scripts in what's being said, and checks them against the firm's own rules. All of it runs on the laptop.

### Target user and buyer
- **Sector:** professional services: law, accounting, wealth management
- **User:** staff who take calls on Zoom, Teams or RingCentral at their laptop: paralegals, bookkeepers, accounts payable, office managers
- **Buyer:** managing partner or office manager at firms of **10–200 people** with no security team
- **Why them:** they hold client funds, bank details and Social Security numbers, and scammers know it. Large companies have Microsoft Defender and security staff. These firms don't.

### Problem
- Phone scams aimed at staff are rising, and AI voice cloning makes them convincing. In Aug 2026, attackers cloned colleagues' voices to target Point72, Citadel and Millennium.
- Verizon's 2026 report (cited by CPA Practice Advisor): phone scams succeed **~40% more often per attempt** than phishing emails. Only **10%** of security leaders train staff to spot cloned voices, vs 73% for email phishing.
- Today's tools check **who** is calling (the number, the caller's organization). Scammers use new or spoofed numbers. Almost nothing checks **what** is being said, except Google on Pixel phones.
- The standard advice is "call back on the number on file." That relies on a stressed employee remembering it mid-call.

### The real story behind it
A lawyer friend working on a money laundering case got a call on her mobile from someone posing as a government official. They said she was under scrutiny for breaking the law and could be sent to China, told her not to tell her teammates, and asked for her bank details. She gave them.

The warning signs: **posing as an authority, secrecy, a threat, a request for bank details, and inside knowledge of her real case.**

Note: she was called on her **mobile**. Our laptop app would catch the same script on a work line or a call answered on her Mac. For calls held to the ear, the answer is the "check with a colleague" button.

### Scenarios

| Who calls | What they say | What they want |
|---|---|---|
| Fake government official | "You're under investigation. Don't tell your colleagues" | Bank details, a payment |
| Fake vendor | "We changed banks, update our details before Friday's payment" | Payment sent to their account |
| Fake IT support | "Your account is compromised. Read me the code we just sent" | A login code (how MGM was breached in 2023) |
| Cloned partner's voice | "I'm boarding a flight. Wire the escrow funds now" | An urgent wire with no checks |

### Solution
1. **Listens locally:** captures call audio on the Mac (Zoom, Teams, RingCentral, and iPhone calls answered on the Mac if the test passes)
2. **Transcribes locally:** Whisper, on the laptop. English and Mandarin
3. **Checks the script locally:** a small model (via Ollama) looks for scam tactics: posing as an authority, urgency, secrecy, threats, asking for credentials or bank changes, skipping approval
4. **Checks the firm's rules:** the firm sets rules once, e.g. "We never change vendor bank details by phone." "IT never asks for your code."
5. **Warns in plain words:** "This breaks your firm's rule: bank changes need a callback. Vendor's number on file: …" For high risk, a full-screen warning that a bank or login window can't hide.
6. **Verifies the claim (Surge):** for an unknown caller, searches **only the claimed company or agency name** to find its real public number.
7. **Check with a colleague:** one tap sends a heads-up to a trusted person the firm picks. It breaks the "don't tell anyone" isolation and works for any call, even on a phone.

**Privacy by design**
- Audio and transcripts never leave the laptop and are not saved after the call
- The employer gets **no transcripts**, only anonymous counts ("3 vendor-scam alerts this month"). It protects staff without monitoring them
- The only thing sent online is the claimed company name, and it shows in the "what left this device" log

### User flow

**Setup (once, by the office manager)**
1. Install the app and allow audio access
2. Add 3–5 firm rules (templates provided)
3. Add the vendor and bank contact list (stored encrypted on the laptop)
4. Pick a trusted colleague for "check with a colleague"

**During a call (the employee)**
1. A call starts on Zoom or Teams, and the app shows a small "Listening locally" badge
2. A live risk meter sits next to the call window: low, watch, danger
3. At "watch," the app shows a short note: "Caller is claiming authority and asking for secrecy"
4. At "danger," a full-screen warning shows the tactic, the rule broken, the real number found, and the next step: "Hang up and call back on …"
5. One tap: "Check with a colleague" or "Mark as safe"

**After the call**
- A summary card ("Possible government-impersonation scam, 3 warning signs"), stored locally and deletable
- The admin dashboard shows anonymous counts only

**Training mode (stretch, uses Gradium)**
- Gradium voice cloning, with consent, makes "the managing partner" call staff with a fake urgent wire request. Staff practice, and the app scores how they did. This fills the 10% gap in cloned-voice training.

---

## 6. Competitors

| Product | What it does | Gap we fill |
|---|---|---|
| Microsoft Defender for Teams | In-call warning when a call seems to impersonate a known organization | Teams only. Based on who's calling, as far as Microsoft describes it. Needs a security team |
| Polygraf Meeting Guard | Joins Zoom/Teams/Meet as a visible bot to detect deepfakes and data leaks | Enterprise. Meetings, not calls. A bot in the call is awkward |
| Google Pixel Scam Detection | On-device conversation analysis | Pixel phones only, consumers, beeps without explaining |
| Truecaller, Hiya | Number lookup, AI-voice detection | Miss new numbers. Voice detection weakens as AI voices improve |
| KnowBe4 and other training | Teaches staff beforehand | Doesn't help during the call |

---

## 7. Fit against the judging criteria

| Criterion | Fit | Our evidence |
|---|---|---|
| **Privacy: what leaves the device** | ✅ | Only the claimed company name, shown in a log |
| **Privacy: who can read it** | ✅ | Only the employee, on their laptop. Not the employer, not us |
| **Privacy: can you prove it** | ✅ | Wi-Fi-off demo plus the "what left this device" log |
| **Privacy: would anyone use it** | ✅ | The friend's story plus the vishing stats |
| **Startup: who it's for** | ✅ | Professional firms of 10–200 people with no security team |
| **Startup: would they pay** | ✅ | One stopped wire covers years of seats. Price to test: $10–20 per seat per month |
| **Startup: why this team** | ✅ | Coco: 5 years of PM in conversational AI and voice agents (SleekFlow), a 3rd place at the Lovable hackathon with RelayAI (real-time call transcription), and direct access to a victim and her law firm |
| **Surge: how central the API is** | ⚠️ | A real verification step, but not the whole product. Make it visible in the demo |
| **Surge: how well it works** | — | Test with 5 real company names |
| Gradium (no prize) | ✅ | Cloned-voice demo opener, plus training mode |

---

## 8. Risks and open questions

| Risk | Plan |
|---|---|
| Can the Mac capture Continuity call audio? | Test first (see the project plan). If it fails, Zoom/Teams only |
| Massachusetts requires everyone's consent to record | We don't store audio or transcripts. Ask the lawyer friend if live transcription counts as recording, and show a "this call is checked locally" notice |
| False alarms on real vendor bank changes | Warn "verify first," not "this is fraud" |
| Microsoft expands Teams protection | We cover every calling app and need no security team |
| Rules on pre-existing code | Ask an organizer Saturday |
| Using the friend's story | Get her OK. No identifying details |
