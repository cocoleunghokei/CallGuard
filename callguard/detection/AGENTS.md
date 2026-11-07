# Lane: Detection (scam check + firm rules)

Read the root [AGENTS.md](../../AGENTS.md) first. You own `callguard/detection/` and `tests/detection/` only.
Coco owns the wording of `prompt.md` and `rules.json`. Coco signs off on changes to them.

## Delivers
`check(transcript: str, rules: list[Rule]) -> ScamCheck`, where `transcript` is the rolling last ~30 s of text. It always returns a valid `ScamCheck`, even if the model fails, in which case it returns `risk: "low"` with a reason saying the check failed.

## Tasks
**P0**
- [ ] `prompt.md`: system prompt v1 for the scam check, asking for JSON only
- [ ] `ollama_client.py`: call `http://localhost:11434` with `qwen2.5:7b` (`format: "json"`, temperature 0). Allow switching to `qwen2.5:3b` with the `CALLGUARD_MODEL` env var
- [ ] `parse.py`: validate the model's JSON against `ScamCheck`, drop unknown tactics, never crash
- [ ] `rules.json` with 3–5 firm rules, plus `rules.py` to load them and add matching `rules_broken`
- [ ] `tests/detection/scripts/`: the 7 test scripts from [plan section 6](../../hack1984/project-plan.md), with expected risk levels
- [ ] Eval script: run all 7 scripts against the live model and print a pass/fail table. Target: at least 5 of 6 English scripts correct

**P1**
- [ ] Mandarin script 7 passes
- [ ] Tune so urgency alone is never "danger" (script 5)

## Rules for this lane
- Localhost Ollama only. No cloud models
- Unit tests use a fake model response. Only the eval script needs Ollama running
- Warnings say "verify first," never "this is fraud"

## Status
- (none yet)
