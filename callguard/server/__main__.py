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
from callguard.server.pipeline import Pipeline

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


def fake_call_task(script: str, speed: float):
    async def run(hub: Hub) -> None:
        await hub.wait_for_client()  # don't play the call to an empty room
        pipeline = Pipeline(hub.broadcast)
        try:
            await pipeline.run_fake(script, speed=speed)
        finally:
            pipeline.close()
    return run


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    load_env()
    tasks = [fake_call_task(args.fake, args.fake_speed)] if args.fake else []
    app = create_app(tasks=tasks)
    if not args.browser:
        logging.getLogger("callguard.server").info(
            "native window not built yet (SRV-11); serving for the browser")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
