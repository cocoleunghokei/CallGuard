"""python -m callguard.server [--browser] [--port 8000]

SRV-11 (native pywebview window as the default) is not built yet, so for now
both modes serve http://localhost:8000; --browser is the dev path.
"""
from __future__ import annotations

import argparse
import logging

import uvicorn

from callguard.server.app import create_app


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m callguard.server")
    p.add_argument("--browser", action="store_true",
                   help="dev only: serve http://localhost:PORT for a browser, no native window")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    app = create_app()
    if not args.browser:
        logging.getLogger("callguard.server").info(
            "native window not built yet (SRV-11); serving for the browser")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
