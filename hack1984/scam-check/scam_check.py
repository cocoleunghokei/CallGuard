"""
Callguard scam check: transcript -> local Ollama model -> risk JSON.
Standard library only. Needs Ollama running locally (it is, if `ollama list` works).

Run all 7 test scripts:   python3 scam_check.py
Pick a model:             python3 scam_check.py --model qwen2.5:3b
Check your own text:      python3 scam_check.py --text "Hi, this is IT, read me the code we sent"
"""
import argparse, json, sys, time, urllib.request
from pathlib import Path

HERE = Path(__file__).parent
OLLAMA = "http://localhost:11434/api/chat"
TACTICS = ["authority", "secrecy", "urgency", "threat", "credential_request", "bank_change", "bypass_approval"]

SYSTEM = """You protect staff at a small professional firm (law, accounting, wealth management) from phone scams.
You read a live call transcript and judge whether the CALLER is running a scam script.

Scam tactics to look for:
- authority: claims to be police, government, a regulator, a bank, IT, or a senior partner
- secrecy: tells the employee not to tell colleagues, family or anyone
- urgency: pressure to act right now, before a deadline, or on this call
- threat: arrest, investigation, deportation, fines, account closure
- credential_request: asks for passwords, one-time codes, MFA codes, PINs
- bank_change: asks to change payee bank details or send money to a new account
- bypass_approval: asks to skip the normal approval or callback process

Calibration:
- One tactic alone (a deadline, a normal bank calling about a charge) is usually "low" or "watch".
- A caller who tells you to hang up and call the official number on your card is a GOOD sign.
- "danger" means a combination (authority + secrecy/threat) or any request for credentials, bank changes or money,
  or any firm rule broken.
- Say "verify first", never "this is fraud".

Firm rules (report the id of any rule the caller is asking the employee to break):
{rules}

Reply with JSON only, exactly these keys:
{{"risk": "low|watch|danger", "tactics": [subset of {tactics}], "claimed_identity": string or null,
 "rules_broken": [rule ids], "reason": one plain sentence for the employee, "next_step": one plain sentence}}"""


def load_rules():
    rules = json.loads((HERE / "firm_rules.json").read_text())
    return rules, "\n".join(f'- {r["id"]}: {r["text"]}' for r in rules)


def check(transcript, model, rules_text, rules=(), timeout=180):
    body = {
        "model": model,
        "stream": False,
        "keep_alive": "60m",  # keep the model in memory so the demo never waits for a reload
        "format": "json",
        "options": {"temperature": 0},
        "messages": [
            {"role": "system", "content": SYSTEM.format(rules=rules_text, tactics=TACTICS)},
            {"role": "user", "content": f"Transcript so far:\n{transcript}"},
        ],
    }
    req = urllib.request.Request(OLLAMA, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        content = json.loads(r.read())["message"]["content"]
    out = json.loads(content)
    # Normalise so the screen never gets junk
    out["risk"] = out.get("risk") if out.get("risk") in ("low", "watch", "danger") else "watch"
    out["tactics"] = [t for t in out.get("tactics") or [] if t in TACTICS]
    # A rule only counts if a tactic that triggers it was actually detected.
    # Stops the model blaming "bank changes" on a call that never mentioned a bank.
    triggers = {r["id"]: set(r.get("tactics", [])) for r in rules}
    out["rules_broken"] = [r for r in out.get("rules_broken") or []
                           if r in triggers and triggers[r] & set(out["tactics"])]
    if out["rules_broken"] and out["risk"] != "danger":
        out["risk"] = "danger"  # breaking a firm rule is always danger
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen2.5:7b")
    ap.add_argument("--text", help="check one transcript instead of the test set")
    args = ap.parse_args()
    rules, rules_text = load_rules()

    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3)
    except Exception:
        sys.exit("Ollama is not running. Start the Ollama app, or run `ollama serve` in another terminal.")

    if args.text:
        print(json.dumps(check(args.text, args.model, rules_text, rules), indent=2, ensure_ascii=False))
        return

    cases = json.loads((HERE / "test_scripts.json").read_text())
    passed = 0
    for c in cases:
        t0 = time.time()
        try:
            out = check(c["transcript"], args.model, rules_text, rules)
        except urllib.error.HTTPError as e:
            sys.exit(f"Ollama error {e.code}: {e.read().decode()[:200]}\nDid you `ollama pull {args.model}`?")
        ok = out["risk"] in c["expected"]
        passed += ok
        print(f'{"PASS" if ok else "FAIL"}  #{c["id"]} {c["name"]:<32} got={out["risk"]:<6} '
              f'want={"/".join(c["expected"]):<11} {time.time()-t0:4.1f}s  tactics={out["tactics"]} '
              f'rules={out["rules_broken"]}')
        print(f'      reason: {out.get("reason")}')
    print(f"\n{passed}/{len(cases)} correct with {args.model}  (plan target: at least 5 of 6)")


if __name__ == "__main__":
    main()
