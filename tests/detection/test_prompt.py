"""DET-1: prompt.md stays in sync with the contracts and the copy rules (prd §9.3)."""
import re
from pathlib import Path

from callguard.shared.contracts import SAFE_SIGNALS, TACTICS

PROMPT = (Path(__file__).parents[2] / "callguard" / "detection" / "prompt.md").read_text(encoding="utf-8")
SCRIPTS = Path(__file__).parent / "scripts"


def test_every_tactic_and_safe_signal_is_defined():
    for name in TACTICS + SAFE_SIGNALS:
        assert f"- `{name}`:" in PROMPT, name


def test_no_unknown_names_defined():
    defined = set(re.findall(r"^- `([a-z_]+)`:", PROMPT, re.M))
    assert defined <= set(TACTICS) | set(SAFE_SIGNALS) | {"caller", "you", "clear", "hint"}


def test_json_only_caller_only_verbatim_verify_first():
    p = PROMPT.lower()
    assert "json object and nothing else" in p
    assert "only `caller:` lines count" in p
    assert "word for word" in p and "80 characters" in p
    assert "verify first" in p
    assert "never say the call is fraud" in p


def test_prompt_examples_do_not_leak_eval_lines():
    """Tactic examples must not copy script lines, or the eval would be measuring memorised text."""
    examples = re.findall(r'Example: "([^"]+)"', PROMPT)
    assert len(examples) == len(TACTICS)
    script_text = " ".join(p.read_text(encoding="utf-8").lower() for p in SCRIPTS.glob("*.txt"))
    for ex in examples:
        assert ex.lower() not in script_text, ex
