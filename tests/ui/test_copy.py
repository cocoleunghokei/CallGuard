"""T3 / UI-2, UI-3, UI-15: fixed UI wording matches the brief and the PRD."""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
UI = ROOT / "ui"
COPY_JS = (UI / "copy.js").read_text(encoding="utf-8")

# Design brief (hack1984/ui-tasks.md, Part A): exact plain words per tactic.
BRIEF_PLAIN = {
    "authority": "Claims to be an official or someone senior",
    "secrecy": "Asks you to keep it secret",
    "urgency": "Rushing you",
    "threat": "Threatens you or the firm",
    "credential_request": "Asks for a code or password",
    "bank_change": "Wants to change bank details",
    "bypass_approval": "Wants you to skip the usual approval",
    "payment_request": "Asks you to send money",
    "remote_access": "Asks you to install software or give screen access",
    "personal_data_request": "Asks for client or personal data",
    "inside_knowledge": "Uses real details to sound legitimate",
}
BANNED = re.compile(r"\b(fraud\w*|scam|scams|scammer\w*|attack\w*)\b", re.I)


def js_map(name):
    block = re.search(rf"export const {name} = \{{(.*?)\n\}};", COPY_JS, re.S).group(1)
    return {k: v.replace('\\"', '"') for k, v in re.findall(r'^\s*(\w+): "((?:[^"\\]|\\.)*)",?$', block, re.M)}


def test_plain_words_match_the_brief():
    assert js_map("PLAIN") == BRIEF_PLAIN


def test_every_tactic_has_a_short_label():
    from_contracts = re.search(r"Tactic = Literal\[(.*?)\]", (ROOT / "callguard/shared/contracts.py").read_text(), re.S).group(1)
    tactics = set(re.findall(r'"(\w+)"', from_contracts))
    assert tactics <= set(js_map("SHORT")), tactics - set(js_map("SHORT"))
    assert tactics <= set(BRIEF_PLAIN)


def test_say_lines_match_prd_18_3():
    prd = (ROOT / "hack1984/prd.md").read_text(encoding="utf-8")
    section = prd.split('### 18.3 "Say this" lines', 1)[1].split("\n### ", 1)[0]
    rows = re.findall(r'^\| (\w+)(?: \([^)]*\))? \| "(.+)" \|$', section, re.M)
    assert len(rows) >= 10
    assert js_map("SAY") == dict(rows)


def test_no_banned_words_in_ui_copy():
    files = [UI / "index.html", *sorted(UI.glob("*.js"))]
    for f in files:
        hits = BANNED.findall(f.read_text(encoding="utf-8"))
        assert not hits, f"{f.name}: {hits}"
