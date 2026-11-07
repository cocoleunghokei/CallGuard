# Callguard eval suite (HACK1984)

Owner: Coco (Lead) · Built by: Detection lane · Status: v1 draft for review · Last updated: Sat Nov 7, 2026

Read with: [prd.md](prd.md) §3.3 (success measures), §4 (scenario catalog), §6 (confidence score), §15 (testing), and the Detection lane's [AGENTS.md](../callguard/detection/AGENTS.md).

This document specifies the eval suite behind **DET-9** (eval script) and **DET-11** (tuning). It says what we measure, on which data, how a beat passes or fails, what numbers the summary prints, and which results block a merge. It does not change any contract; where the eval needs something from another lane, it is listed under [§10 Needs](#10-needs-and-open-questions).

---

## Contents

1. [Why an eval suite](#1-why-an-eval-suite)
2. [Three layers](#2-three-layers)
3. [The dataset](#3-the-dataset)
4. [How one script is run](#4-how-one-script-is-run)
5. [Pass/fail rules](#5-passfail-rules)
6. [Metrics and the summary line](#6-metrics-and-the-summary-line)
7. [Gates: what blocks a merge](#7-gates-what-blocks-a-merge)
8. [Command line and output](#8-command-line-and-output)
9. [Requirements (EVAL-)](#9-requirements-eval-)
10. [Needs and open questions](#10-needs-and-open-questions)

---

## 1. Why an eval suite

The demo stands or falls on two claims: **Callguard catches the script** (S1–S4 reach `danger` by the giveaway line) and **it stays quiet on real calls** (no benign twin reaches `danger`). Unit tests prove the scorer and parser do what §6 says; they cannot prove that `qwen2.5:7b` plus our prompt finds the right tactics in real sentences. The eval suite is the only thing that does, and its table is the evidence we show judges when they ask "how often does it false-alarm?"

It also makes tuning safe. Every prompt or weight change during DET-11 is judged by the same numbers, so a fix for S4 that breaks B3 is caught before it reaches `main`.

**Privacy still applies.** The eval runs on synthetic, scripted calls only, never on recorded audio or real transcripts. Output goes to stdout. No real call data is ever added to the dataset.

---

## 2. Three layers

| Layer | What it checks | Needs | Runs in | When |
|---|---|---|---|---|
| **L1 Offline eval** | The eval harness, scorer, guards, rules and smoothing, fed with **recorded model outputs** for each beat | Nothing | `pytest` (`tests/detection/test_eval.py`) | Every commit |
| **L2 Live model eval** | Prompt + `qwen2.5:7b` + scorer on every script, beat by beat | Ollama | `python -m callguard.detection.eval` | Every prompt, weight or rule change; each checkpoint |
| **L3 Pipeline timing** | Giveaway line → `danger` on screen, through Server and UI | Ollama, Server | `python -m callguard.server --fake …` + `SRV-2` timing log | Sat 19:00, Sat 22:00, before the backup video |

L1 keeps the suite honest without a model: if someone changes a weight, the L1 test shows which scripts flip. L2 is DET-9 proper. L3 is out of the Detection lane; it is listed here so the latency targets in §3.3 have one home.

---

## 3. The dataset

### 3.1 Files

One file per scenario in `tests/detection/scripts/`, in the §15.2 format, which `audio.fake_stream()` also reads. Names follow the catalog: `s1_government.txt`, `s2_vendor_bank.txt`, `s3_it_code.txt`, `s4_partner_wire.txt`, …, `b1_vendor_invoice.txt`, `b2_colleague_deadline.txt`, `b3_real_bank.txt`, `b7_you_say_it.txt`, ….

| Set | Scams | Benign twins | Priority |
|---|---|---|---|
| **P0** | S1, S2, S3, S4 | B1, B2, B3, B7 | Must pass (DET-8 P0 set) |
| **P1** | S5–S10 | B4, B5, B6 | Broader coverage for Q&A |
| **Variants** (P1) | Robustness copies of P0 scams, §3.4 | Robustness copies of P0 twins | Report only, never a gate |

The plan's six scripts (plan §6) map to S1, S2, S3, B1, B2, B3. Script 7 (Mandarin) was removed with Mandarin; the Detection lane's task list still says "7 scripts" and should read "the P0 set".

### 3.2 Header fields

The §15.2 headers stay as they are. The eval adds **optional** header lines, so `fake_stream()` (which skips `#` lines) is unaffected:

```
# id: s1_government
# set: p0                       # p0 | p1 | variant
# kind: scam                    # scam | twin
# twin_of: -                    # for twins: the scam it mirrors, e.g. b3 -> s5
# expect: low, watch, danger, danger
# giveaway: 3                   # caller line marked ⚡ in prd §4
# gate: 4                       # caller line marked 🔒 (omit if never)
# tactics: authority, threat, secrecy, bank_change    # must appear by the last beat
# rules: government_never_calls_for_payment_or_bank_details, never_keep_calls_secret
# claimed: Department of Justice                        # or "-" for none
caller: Hi, this is Officer Chen from the Department of Justice.
…
```

- `expect` allows a set per beat with `|`, for the catalog's "low/watch" rows: `# expect: low|watch` for B3 and B5. A beat passes if the call risk is any listed level.
- `expect`, `giveaway` and `gate` count **caller** lines only, as in §15.2.
- `tactics`, `rules` and `claimed` are checked once, after the last beat (§5.2). Use tactic names from `contracts.TACTICS`. Until LEAD-1 adds the v2 tactics, a v2 tactic in a header is reported as `n/a`, not a failure.

### 3.3 Writing scripts

- Every line is English and sounds spoken: short sentences, fillers allowed ("um, so").
- Each scam has at least one `you:` line, so the window is speaker-labelled the way a real call is.
- Each twin shares surface features with its scam (authority, money, a bank, urgency) so it tests the guards and safe signals, not just "no scary words".
- B7 puts the scary words in a `you:` line. It is the check for guard G4.
- Coco signs off on every script and its `expect` line (DET-8). Changing an `expect` line to make a run pass needs Coco's sign-off in the commit message.

### 3.4 Robustness variants (P1)

Generated by hand, stored as normal scripts with `set: variant` and `id: s1_government__mishear` etc. One variant type per file:

| Variant | What changes | Why |
|---|---|---|
| `__mishear` | Likely Whisper errors on key words ("routing" → "rooting", "MFA" → "and FA", "escrow" → "s grow") | §16: Whisper mishears a key phrase |
| `__paraphrase` | Same beats, different wording, no stock phrases | The model must read meaning, not keywords |
| `__chatty` | Two to three filler caller lines between beats | The giveaway may arrive late in a 30 s window |
| `__split` | The giveaway sentence split over two chunks | 3 s chunks cut sentences in half |

Variants are reported in their own summary line and never block a merge.

---

## 4. How one script is run

The eval reproduces what the Server does in a call, minus audio, so a pass in the eval means the same sequence on screen.

1. **Load** the script and its headers. Assign each line a 3 s slot (`start = 3*i`, `end = start + 3`), as `fake_stream(speed=0)` does.
2. **For each caller line** (a "beat"):
   1. Build the rolling window: every line, both speakers, whose `end` is within the last 30 s, speaker-labelled (`caller: …`, `you: …`).
   2. Call `check(window, rules)` (DET-7) with the real Ollama client. Record the returned `ScamCheck`, the wall-clock latency and whether `source` is `model`, `fast` or `fallback`.
   3. Apply **call-level smoothing** (C10, §6.7) to get the call risk: rises immediately; `danger` is sticky to the end of the script; `watch` drops to `low` after 3 consecutive `low` checks.
   4. Compare the call risk with `expect` for that beat.
3. **After the last beat**, compare the union of tactics, the union of `rules_broken`, and the last non-null `claimed_identity` with the headers.
4. Repeat the whole script `--runs` times (default 1; 3 for a checkpoint run) with a fresh call state each time.

`you:` lines are never checked on their own; they only enter the window, like in the Server.

---

## 5. Pass/fail rules

### 5.1 Per beat

A beat **passes** when the call risk is in its `expect` set. The table also shows the raw window risk and confidence, so a beat that passes only because danger was sticky is visible.

Beats are tagged in the table:
- `⚡` the giveaway beat. A scam **must** be `danger` here.
- `🔒` the gate beat. Recorded as `gate ✔` when the `ScamCheck` would make the gate eligible under §7 (C14): `danger` with an ask tactic or a broken rule.
- `early` a scam beat **before** the giveaway that is already `danger`. Not a failure on its own (the expect line decides), but counted, because danger before the giveaway on stage looks like a false alarm.

### 5.2 Per script

| Check | Scam passes when | Twin passes when |
|---|---|---|
| Risk sequence | Every beat passes | Every beat passes |
| **Catch** | Call risk is `danger` at the giveaway beat | n/a |
| **Quiet** | n/a | Call risk is never `danger` on any beat |
| Tactics | Every header tactic was found by some beat (extra tactics allowed) | Reported only |
| Rules | Every header rule was broken by some beat | No rule broken (reported; a broken rule on a twin is a warning, not a gate) |
| Claimed identity | Last non-null `claimed_identity` matches the header, case-insensitive, ignoring "the" | Reported only |
| Grounding | Every `evidence.quote` is a substring of its window (after C5 should be 100%) | Same |

**Catch** and **Quiet** are the headline results. The other checks explain *why* a script failed and feed tuning.

### 5.3 Flakiness

With `--runs N`, a script's result is its **worst** run, and the summary prints `stable 7/8` (scripts that gave the same call-risk sequence in every run). Temperature 0 makes Ollama nearly deterministic, not fully, and on stage we get one run.

---

## 6. Metrics and the summary line

Every row of prd §3.3 that says "`DET-9` eval table" is computed here:

| Metric | Definition | Target (P0) | Target (P1) |
|---|---|---|---|
| `scams danger` | Scams caught (danger at the giveaway beat) / scams run | 4/4 (S1–S4) | ≥ 9/10 |
| `twins danger` | Twins that ever reached danger / twins run | 0/4 (B1, B2, B3, B7) | 0/7 |
| `twins low` | Twins whose final call risk is `low` / twins run | — | ≥ 5/7 |
| `plan scripts` | Plan scripts 1–6 (S1–S3, B1–B3) with every beat passing | ≥ 5/6 | — |
| `beats` | Beats passing / beats run | Reported | Reported |
| `early danger` | Scam beats in danger before their giveaway | Reported (want 0) | Reported |
| `tactic recall` | Header tactics found / header tactics, over scams | Reported | Reported |
| `rule recall` | Header rules broken / header rules, over scams | Reported | Reported |
| `identity` | Scams with the right claimed identity / scams with a `claimed` header | Reported | Reported |
| `fallback` | Checks with `source: fallback` / all checks | Reported (want 0) | Reported |
| `latency` | p50 and p95 of `check()` wall time, ms | p95 ≤ 5 s (Q5) | p95 ≤ 5 s |
| `stable` | Scripts with identical call-risk sequences across runs | Reported | Reported |

Latency here is model time only. The end-to-end target (giveaway spoken → danger on screen ≤ 10 s) is measured in L3 with the `SRV-2` timing log and a stopwatch on the Zoom run.

The summary line extends the one in prd §15.3:

```
SUMMARY  scams danger 4/4 · twins danger 0/4 · plan scripts 6/6 · beats 23/24 · early 0
         tactics 15/16 · rules 6/6 · identity 4/4 · fallback 0/24 · p50 2.3 s · p95 3.1 s · stable 8/8
P0 GATE  PASS
```

---

## 7. Gates: what blocks a merge

The eval exits non-zero when a gate fails, so it can be pasted into Status as pass/fail without reading the table.

| Gate | Rule | Applies to |
|---|---|---|
| **P0 catch** | `scams danger` = 4/4 on the P0 set | Every prompt, weight or rules change on `lane/detection` |
| **P0 quiet** | `twins danger` = 0/4 on the P0 set | Same |
| **P0 latency** | p95 ≤ 5 s on the demo Mac | Checkpoint runs only (other machines are slower or faster) |
| **P1 targets** | `scams danger` ≥ 9/10, `twins danger` 0/7, `twins low` ≥ 5/7 | Only once the P1 set is in; reported before then |

**Merge rule for DET-11:** a change to `prompt.md`, `rules.json` or the `score.py` weights is merged only with a Status line that pastes the `SUMMARY` and `P0 GATE` lines from a run on the commit being merged. A change that drops any gate from PASS to FAIL is not merged, even if it fixes something else.

**Tuning order** when a gate fails, cheapest first: (1) the script is wrong (Coco decides); (2) prompt wording for one tactic or safe signal; (3) rule `keywords` / `requires`; (4) a weight or combo in `score.py` (update `test_score.py` and prd §6.6 together); (5) the window length. Changing the model is last, and 3b is not a fallback (prd Q5).

---

## 8. Command line and output

```bash
python -m callguard.detection.eval                         # P0 set, 1 run, live Ollama
python -m callguard.detection.eval --set p0,p1 --runs 3    # checkpoint run
python -m callguard.detection.eval --only s2_vendor_bank -v
python -m callguard.detection.eval --replay                # L1: recorded model outputs, no Ollama
```

| Flag | Meaning | Default |
|---|---|---|
| `--set` | Comma list of `p0`, `p1`, `variant` | `p0` |
| `--only` | Comma list of script ids | all in the set |
| `--runs` | Runs per script | 1 |
| `--model` | Ollama model (same as `CALLGUARD_MODEL`) | `qwen2.5:7b` |
| `--replay` | Use recorded model outputs from `tests/detection/fixtures/model_outputs/` instead of Ollama | off |
| `--record` | Save this run's raw model outputs as replay fixtures (synthetic scripts only) | off |
| `--json` | Print one JSON object per beat to stdout instead of the table | off |
| `-v` | Also print the evidence quotes (≤ 80 chars each) and `reason` per beat | off |

Output is the §15.3 table plus the columns below, then the summary:

```
script            beat   expect      call    win     conf  tactics                    rules  ms    ok
s1_government     1      low         low     low     0.31  authority                  -      2140  ✔
s1_government     2      watch       watch   watch   0.71  authority,threat           -      2380  ✔
s1_government     3 ⚡   danger      danger  danger  0.99  authority,threat,secrecy   1      2410  ✔
s1_government     4 🔒   danger      danger  danger  1.00  …,bank_change              2      2290  ✔ gate ✔
b3_real_bank      1      low|watch   low     low     0.16  authority (+callback)      -      1980  ✔
…
```

**No transcript on disk.** The eval never writes window text. `--record` writes the raw model JSON for synthetic scripts only, so L1 can replay it; it refuses to run unless every script path is under `tests/detection/scripts/`. Results go to stdout; the Status line is pasted by hand.

Until LEAD-1 lands, `conf` is computed from the v1 `ScamCheck` by the eval's own copy of the scorer, or shown as `-`; the table must still run.

---

## 9. Requirements (EVAL-)

All Detection lane, under DET-9 / DET-11. Commit with the ID (`EVAL-3: smoothing in eval`).

| ID | P | Requirement | Done when | Depends on |
|---|---|---|---|---|
| EVAL-1 | P0 | Script loader: §15.2 format plus the §3.2 optional headers; `low\|watch` expect sets; validates that `expect` has one entry per caller line and `giveaway`/`gate` are in range | Unit tests, including a malformed header | DET-8 |
| EVAL-2 | P0 | Runner: 3 s slots, rolling 30 s speaker-labelled window, one `check()` per caller line, latency per check (§4) | Runs S1 against a fake client | DET-7 |
| EVAL-3 | P0 | Call-level smoothing in the eval (rise, sticky danger, watch decay), matching §6.7; switch to the Server's function once SRV-7 is on `main` | Unit tests mirror SRV-7's | — |
| EVAL-4 | P0 | Per-beat and per-script checks (§5), P0 metrics and summary line (§6), exit code from the gates (§7) | L1 test: a replay that misses S3 exits non-zero | EVAL-1..3 |
| EVAL-5 | P0 | P0 scripts with full headers: S1–S4, B1, B2, B3, B7 | Coco signs off | DET-8 |
| EVAL-6 | P0 | `--replay` and `--record`; recorded outputs for the P0 set; `tests/detection/test_eval.py` runs the whole P0 set offline in `pytest` | `pytest tests/detection` green with no Ollama | EVAL-4 |
| EVAL-7 | P0 | First live run on the demo Mac; table and summary in Status | Status line with `P0 GATE` | EVAL-4, Ollama |
| EVAL-8 | P1 | `--runs`, worst-run result and `stable` count | Checkpoint run uses `--runs 3` | EVAL-4 |
| EVAL-9 | P1 | P1 scripts (S5–S10, B4–B6) with headers; P1 targets in the summary | Coco signs off | EVAL-5 |
| EVAL-10 | P1 | Robustness variants for S1–S4 and B3 (§3.4) with their own summary line | Reported in Status | EVAL-5 |
| EVAL-11 | P1 | `--json` per-beat output | Pipes to `jq` | EVAL-4 |

**Timing.** Fits the `Eval + tuning (DET-9, 11)` slot in the prd schedule (Sat 17:30, 270 min): EVAL-1..6 by ~19:00 so the first full run has a number, EVAL-7 before the Sat 22:00 P0 decision, EVAL-8..11 only if P1 starts.

---

## 10. Needs and open questions

| # | Item | From | Proposal |
|---|---|---|---|
| N1 | v2 `ScamCheck` fields (`confidence`, `evidence`, `safe_signals`, `source`) and v2 tactics | Coco (LEAD-1) | The eval runs on v1 meanwhile and shows `-` / `n/a` for missing fields |
| N2 | SRV-7 smoothing as an importable pure function (`smooth(state, check) -> state`) so the eval and the Server agree | Server, via Coco | Eval keeps its own copy (EVAL-3) until then, with the same unit tests |
| N3 | Update the Detection task list: "all 7 scripts … 5 of 6" → "the P0 set, gates in eval-suite.md §7" | Coco (Detection `AGENTS.md`) | One-line edit |
| N4 | Is `--record` (synthetic model JSON written under `tests/`) acceptable under guardrail 1? | Coco | Yes: it is test data from scripts, never a call; the path check enforces it |
| Q1 | Should `early danger` be a gate? Danger at S1 beat 2 on stage would look like a false alarm | Coco | Report only this weekend; revisit if it happens in a run |
| Q2 | Should a broken rule on a twin (e.g. B5 tripping `wires_need_two_approvals`) be a gate? | Coco | Warning only; the Quiet gate already covers what the user sees |
| Q3 | Which machine's latency counts? | Coco | Only the demo Mac; other machines report latency but skip the latency gate |
