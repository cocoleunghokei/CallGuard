"""py2app recipe for Callguard.app. Run ./build.sh (it calls this), not this file directly.

Alias mode (-A): the app points back at this checkout and its Python, so it is
quick to build and picks up code changes without a rebuild. Build it on the
Mac that runs the demo.
"""
from setuptools import setup

BUNDLE_ID = "com.hack1984.callguard"  # keep in sync with callguard/server/window.py

setup(
    app=["callguard_app.py"],
    name="Callguard",
    options={"py2app": {
        "iconfile": "Callguard.icns",
        "plist": {
            "CFBundleName": "CallGuard",
            "CFBundleDisplayName": "CallGuard",
            "CFBundleIdentifier": BUNDLE_ID,
            "CFBundleShortVersionString": "0.1",
            "NSHighResolutionCapable": True,
            "NSMicrophoneUsageDescription":
                "CallGuard listens to your call on this Mac to warn you about scams. "
                "Audio never leaves this device.",
        },
    }},
    setup_requires=["py2app"],
)
