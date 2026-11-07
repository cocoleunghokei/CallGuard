"""python -m callguard.server [--browser] [--fake SCRIPT [--fake-speed N]] [--port 8000]

SRV-11 (native pywebview window as the default) is not built yet, so for now
both modes serve http://localhost:8000; --browser is the dev path.
Keys (TAVILY_API_KEY, EXA_API_KEY, CALLGUARD_*) are read from .env at the repo root.
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import uvicorn

from callguard.server.app import Hub, create_app
from callguard.server.runtime import Runtime

REPO_ROOT = Path(__file__).resolve().parents[2]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m callguard.server")
    p.add_argument("--browser", action="store_true",
                   help="dev only: serve http://localhost:PORT for a browser, no native window")
    p.add_argument("--fake", metavar="SCRIPT",
                   help="replay a scenario script instead of live audio (prd §15.2)")
    p.add_argument("--fake-speed", type=float, default=1.0,
                   help="replay speed for --fake (2 = twice as fast, 0 = instant)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args(argv)
    if args.fake and not Path(args.fake).is_file():
        p.error(f"--fake: no such script: {args.fake}")
    if args.fake_speed < 0:
        p.error("--fake-speed must be >= 0")
    return args


def load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(REPO_ROOT / ".env")


def build_app(args: argparse.Namespace):
    hub = Hub()
    runtime = Runtime(hub)
    tasks = []
    if args.fake:
        async def fake_call(_hub: Hub) -> None:
            await runtime.run_fake(args.fake, speed=args.fake_speed)
        tasks.append(fake_call)
    return create_app(hub, tasks=tasks), runtime


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    load_env()
    app, runtime = build_app(args)
    if not args.browser:
        logging.getLogger("callguard.server").info(
            "native window not built yet (SRV-11); serving for the browser")
    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    finally:
        runtime.close()  # app stops: transcript cleared


if __name__ == "__main__":
    main()
