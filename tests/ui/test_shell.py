"""T2 / UI-1: the shell markup and the view code agree. No browser needed."""
import pathlib
import re

UI = pathlib.Path(__file__).resolve().parents[2] / "ui"


def test_every_element_view_js_uses_exists():
    html = (UI / "index.html").read_text(encoding="utf-8")
    ids = set(re.findall(r'\bid="([\w-]+)"', html))
    used = set(re.findall(r'\$\("([\w-]+)"\)', (UI / "view.js").read_text(encoding="utf-8")))
    assert used, "view.js should look elements up with $()"
    assert used <= ids, f"missing in index.html: {sorted(used - ids)}"


def test_icons_referenced_by_view_exist():
    html = (UI / "index.html").read_text(encoding="utf-8")
    symbols = set(re.findall(r'<symbol id="([\w-]+)"', html))
    used = set(re.findall(r'"#(i-[\w-]+)"', (UI / "view.js").read_text(encoding="utf-8")))
    assert used <= symbols, f"missing icons: {sorted(used - symbols)}"


def test_tokens_defined_for_light_and_dark():
    css = (UI / "styles.css").read_text(encoding="utf-8")
    light, dark = css.split("@media (prefers-color-scheme: dark)", 1)
    for token in ["--bg", "--text", "--muted", "--low", "--watch", "--danger", "--idle", "--focus"]:
        assert f"{token}:" in light, token
        assert f"{token}:" in dark.split("@media", 1)[0], token
    assert "prefers-reduced-motion" in css


def test_system_font_only():
    css = (UI / "styles.css").read_text(encoding="utf-8")
    assert "@font-face" not in css and "@import" not in css
    assert '-apple-system, BlinkMacSystemFont, "Helvetica Neue", sans-serif' in css
