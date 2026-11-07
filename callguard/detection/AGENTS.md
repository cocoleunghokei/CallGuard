# Lane: Detection (scam check + firm rules)

Read the root [AGENTS.md](../../AGENTS.md) first. You own `callguard/detection/` and `tests/detection/` only.
Coco owns the wording of `prompt.md` and `rules.json`. Coco signs off on changes to them.

## Delivers
`check(transcript: str, rules: list[Rule]) -> ScamCheck`, where `transcript` is the rolling last ~30 s of text. It always returns a valid `ScamCheck`, even if the model fails, in which case it returns `risk: "low"` with a reason saying the check failed.

## Tasks
Full list with IDs and "done when": [prd.md §13.3](../../hack1984/prd.md#133-detection--callguarddetection-testsdetection).

**P0**
- [x] `prompt.md`: system prompt v1 for the scam check, asking for JSON only
- [x] `ollama_client.py`: call `http://localhost:11434` with `qwen2.5:7b` (`format: "json"`, temperature 0). Allow switching to `qwen2.5:3b` with the `CALLGUARD_MODEL` env var
- [x] `parse.py`: validate the model's JSON against `ScamCheck`, drop unknown tactics, never crash
- [x] `rules.json` with 3–5 firm rules, plus `rules.py` to load them and add matching `rules_broken`
- [x] `tests/detection/scripts/`: the 6 English test scripts from [plan section 6](../../hack1984/project-plan.md) (scenario details in [prd.md §4](../../hack1984/prd.md)), with expected risk levels
- [ ] Eval script: run all 7 scripts against the live model and print a pass/fail table. Target: at least 5 of 6 English scripts correct

**P1**
- [ ] Tune so urgency alone is never "danger" (script 5)
- [ ] Custom rules (DET-13, [prd.md §8.1](../../hack1984/prd.md#81-customizing-the-rules-p1)): `validate_rules()` and a `load_rules()` that prefers the firm's custom file, falls back to the defaults, and honours `enabled`

## Rules for this lane
- Localhost Ollama only. No cloud models
- Unit tests use a fake model response. Only the eval script needs Ollama running
- Warnings say "verify first," never "this is fraud"

## Status
- [Sat 14:10] Done: DET-8 P0 scripts (s1_government, s2_vendor_bank, s3_it_code, s4_partner_wire, b1_vendor_invoice, b2_colleague_deadline, b3_real_bank, b7_you_say_it) in `tests/detection/scripts/`, §15.2 format + eval-suite §3.2 headers; `tests/detection/test_scripts.py` checks structure (one expect per caller line, giveaway/gate in range, known tactics, twins never danger) | Next: DET-4 rules.json + rules.py | Needs: Coco: sign off the 8 scripts and their `expect` lines. Notes for review: S1/S4 `rules:` also list `never_keep_calls_secret` (secrecy breaks it by §8); S3/S4 have no `claimed:` header (internal IT / a partner, nothing to verify); B7's caller lines are deliberately clean so it tests G4 only. Audio: scripts are ready for `fake_stream()`
- [Sat 14:40] Done: DET-4 `rules.json` (5 P0 rules from prd §8) + `rules.py` (`load_rules(path=None)`, `match_rules(tactics, rules, caller_text="")` with `requires`, `keywords`, `enabled`); `tests/detection/test_rules.py` (18 tests, one block per rule + S1/S4/B7 scenario checks) | Next: DET-1 prompt.md v1 | Needs: Coco: sign off rules.json wording + keywords, and three choices: (1) `wires_need_two_approvals` fires on `bypass_approval` only, not `payment_request`, or B5 (proper two-approval wire) would break it, against prd §6.6's B5 row (rules 0); (2) S1's bank-details ask (`bank_change`) also breaks `no_bank_changes_by_phone`, so S1 shows 3 rules; (3) in practice S1 beat 3 also breaks `never_keep_calls_secret`, so `check()` will give 1.00 there, not the 0.99 in §6.6 (the table row assumes rules 0; test_score.py will reproduce the table as written)
- [Sat 15:05] Done: DET-1 `prompt.md` v1 (role, 11 tactic definitions each with an example line not taken from the scripts, hint/clear, 4 safe signals, caller lines only, verbatim quotes <= 80 chars, reason/next_step <= 20 words, verify first, never "fraud"); `tests/detection/test_prompt.py` keeps it in sync with `TACTICS`/`SAFE_SIGNALS` and checks no example copies an eval line | Next: DET-2 ollama_client.py | Needs: Coco: sign off prompt.md v1 wording. Design choice to review: the model does NOT return `risk`, `confidence` or `rules_broken`; score.py (DET-6) and rules.py (DET-4) compute those so they are deterministic and match §6.6. Demo note: Coco picked S1 (friend calls in live, reading S1's caller lines), S4, B3 as the demo set; I'll prioritise those in DET-11 and add S1 `__mishear` and `__split` variants
- [Sat 15:30] Done: DET-2 `ollama_client.py`: `chat(window_text, post=None, model=None, timeout=8.0) -> str` POSTs `/api/chat` on localhost (`format: json`, temperature 0, `num_ctx` 4096, `num_predict` 512, `keep_alive` 60m), model from `CALLGUARD_MODEL` (default `qwen2.5:7b`); every failure raises `OllamaError` with no transcript text; default transport is `callguard.server.egress.local_ollama_post` (imported lazily, matches the signature on `lane/server`); tests use a fake `post`, plus an AST scan that no detection file imports a network library | Next: DET-3 parse.py | Needs: Server/Coco: merge SRV-3 (`egress.local_ollama_post(url, payload, timeout)`) to main; until then the live path raises `OllamaError`, so the live eval (DET-9) also needs SRV-3 on main
- [Sat 18:20] Done: DET-3 `parse.py`: `parse(raw, window) -> dict | None`, never raises (None only when the reply isn't a JSON object). Keeps evidence only if its quote is in a CALLER line (returns the window's own text, cut to 80 chars); a tactic survives only with surviving evidence; best strength per tactic; unknown tactics/safe signals dropped; identity "null"/"unknown" -> None; reason/next_step cut to 25 words / 160 chars and blanked if they say "scam"/"scammer"/"is fraud" (check() fills a default; "fraud department" allowed); model's risk/confidence/rules_broken ignored. `split_window()` accepts the Server's string of `caller:`/`you:` lines (oldest first, as SRV-2 asks), TranscriptChunk dicts or pairs. `tests/detection/test_parse.py`: 20-case malformed fuzz x 5 windows + targeted tests; full `pytest tests` 325 green | Next: DET-6 score.py | Needs: Server: confirmed, `check(window, rules)` takes the window as one string of `caller: …` / `you: …` lines, oldest first (lists also accepted). Coco: root `pytest` still trips on `hack1984/continuity-audio-test/` (needs sounddevice); `pytest tests` is clean
- [Sat 17:47] Done: DET-6 `score.py` computes noisy-OR confidence, combos, rules, safe signals, and guards G1-G5; `test_score.py` matches all 10 rows of PRD §6.6 to two decimals (17 tests green) | Next: DET-7 check() | Needs: Coco: review §6.6's S1 beat 3 rule-free example against the actual secrecy rule, and sign off existing prompt.md/rules.json wording
- [Sat 17:49] Done: DET-7 `check(window, rules, post=...)` connects the local client, caller-only parser, firm rules, and scorer; every exception or invalid reply yields a valid low-risk fallback explaining the failure; 7 fake-client integration tests pass | Next: DET-9 eval command | Needs: Coco: prompt.md and rules.json wording sign-off remains open
