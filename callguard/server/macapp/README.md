# Callguard.app

Wraps `python -m callguard.server` as a real Mac app, so notifications show the
Callguard icon (`icon.svg`, black and white) and clicking one opens Callguard
instead of Script Editor. The Dock and the menu bar say "Callguard" too.

## Build (on the demo Mac, once)

```bash
callguard/server/macapp/build.sh
```

Use the same Python/venv you run Callguard with. It installs `py2app==0.28.8` if
missing and creates `callguard/server/macapp/dist/Callguard.app` (git-ignored).
Alias mode: the app runs this checkout's code, so code changes need no rebuild.
Moving or deleting the checkout or venv breaks the app; just rebuild.

## Run

Double-click `dist/Callguard.app`, or drag it to the Dock. Live mode by default.
Same options as the command line:

```bash
open callguard/server/macapp/dist/Callguard.app --args --fake tests/detection/scripts/s1_government.txt
```

First run: macOS asks for **microphone** access and **notification** permission.
Allow both. If no banner shows, check System Settings > Notifications > Callguard
(set the style to Banners or Alerts).

## Check

1. Run the `--fake` command above. At the danger beat a banner appears with the
   shield icon and the title "Callguard: verify this call before you act".
2. Click the banner: the Callguard window comes to the front.

Plain `python -m callguard.server` still works; its notifications fall back to
`osascript` (Script Editor icon).

`Callguard.icns` and `icon-1024.png` are generated from `icon.svg`.
