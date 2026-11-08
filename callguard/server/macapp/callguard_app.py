"""Entry point inside Callguard.app (built by build.sh with py2app alias mode).

Running from a real .app bundle is what lets macOS show the Callguard icon on
its notifications and open Callguard (not Script Editor) when one is clicked.
Same options as `python -m callguard.server`, e.g.
`open dist/Callguard.app --args --fake tests/detection/scripts/s1_government.txt`.
"""
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
os.chdir(REPO_ROOT)  # Finder starts apps in "/": relative paths (--fake scripts) resolve from the repo

from callguard.server.__main__ import main  # noqa: E402

if __name__ == "__main__":
    main([a for a in sys.argv[1:] if not a.startswith("-psn_")])  # old macOS adds -psn_ when launched from Finder
