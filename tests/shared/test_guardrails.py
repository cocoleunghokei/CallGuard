"""QA-SH-05..09: repo-wide privacy guardrails (hack1984/qa-test-plan.md §2).

Backstop for the Server lane's SRV-12 tests: these run on every branch, even before
any lane code exists, and fail the build if a guardrail in AGENTS.md §2 is broken.
"""
import ast
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "callguard"
EGRESS = PKG / "server" / "egress.py"


def _py_files():
    return [p for p in PKG.rglob("*.py") if "__pycache__" not in p.parts]


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
            names.add(node.module)
    return names


NETWORK = {"requests", "httpx", "urllib", "urllib3", "http.client", "socket", "aiohttp", "tavily", "exa_py"}
CLOUD_LLM = {"openai", "anthropic", "google.generativeai", "cohere", "mistralai", "groq"}
HOOKS = {"pynput", "keyboard", "Quartz", "mouse"}


@pytest.mark.parametrize("path", _py_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_qa_sh_05_network_imports_only_in_egress(path):
    if path == EGRESS:
        return
    bad = _imports(path) & NETWORK
    assert not bad, f"{path.relative_to(ROOT)} imports {bad}; only server/egress.py may (guardrail 2)"


@pytest.mark.parametrize("path", _py_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_qa_sh_06_no_cloud_llm_sdk(path):
    bad = _imports(path) & CLOUD_LLM
    assert not bad, f"{path.relative_to(ROOT)} imports {bad} (guardrail 5)"


def test_qa_sh_06b_requirements_have_no_cloud_llm():
    req = ROOT / "requirements.txt"
    if not req.exists():
        pytest.skip("requirements.txt not created yet (LEAD-3)")
    names = {re.split(r"[=<>\[ ;]", l.strip())[0].lower() for l in req.read_text().splitlines()
             if l.strip() and not l.startswith("#")}
    bad = names & {"openai", "anthropic", "google-generativeai", "cohere", "mistralai", "groq"}
    assert not bad, f"requirements.txt has cloud LLM SDKs {bad}"


@pytest.mark.parametrize("path", _py_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_qa_sh_07_no_keyboard_or_mouse_hooks(path):
    bad = _imports(path) & HOOKS
    text = path.read_text()
    for token in ("CGEventTapCreate", "addGlobalMonitorForEvents"):
        if token in text:
            bad.add(token)
    assert not bad, f"{path.relative_to(ROOT)} uses {bad}; the pause must never block (prd §7.5)"


def _tracked_files() -> list[str]:
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    return out.stdout.splitlines()


def test_qa_sh_08_no_env_or_api_keys_tracked():
    files = _tracked_files()
    assert not [f for f in files if Path(f).name == ".env"], ".env is tracked (guardrail 10)"
    key = re.compile(r"tvly-[A-Za-z0-9]{16,}|\bEXA_API_KEY\s*=\s*['\"]?[A-Za-z0-9-]{16,}")
    leaks = []
    for f in files:
        p = ROOT / f
        if p.suffix in {".png", ".jpg", ".wav", ".mp4"} or not p.is_file():
            continue
        try:
            if key.search(p.read_text(errors="ignore")):
                leaks.append(f)
        except OSError:
            pass
    assert not leaks, f"possible API key in {leaks}"


AUDIO_WRITE = re.compile(r"\b(sf|soundfile)\.write\(|\bwave\.open\([^)]*['\"]w|\bnp\.save\(|\bnumpy\.save\(")


@pytest.mark.parametrize("path", _py_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_qa_sh_09_no_audio_written_to_disk(path):
    m = AUDIO_WRITE.search(path.read_text())
    assert not m, f"{path.relative_to(ROOT)} writes audio ({m.group(0)}); guardrail 1"
