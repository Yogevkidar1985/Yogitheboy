"""CLI entry point.

    python -m marketwatch run          # loop forever (24/7)
    python -m marketwatch once         # single pass (for cron / GitHub Actions)
    python -m marketwatch fb-login     # save a Facebook session for the facebook source
    python -m marketwatch test-notify  # send a test message to Telegram
"""

from __future__ import annotations

import argparse
import logging
import sys

from .config import load_config


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="marketwatch", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=["run", "once", "fb-login", "test-notify"])
    p.add_argument("-c", "--config", default="config.yaml")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if args.command == "fb-login":
        from .config import load_config as _lc
        from .sources.facebook import interactive_login

        cfg = _lc(args.config) if _config_exists(args.config) else None
        interactive_login(cfg.facebook.state_file if cfg else "fb_state.json")
        return 0

    cfg = load_config(args.config)

    if args.command == "test-notify":
        from .notifiers import build_notifiers

        for n in build_notifiers(cfg):
            n.send_text("✅ MarketWatch: ההתראות עובדות.")
        return 0

    from .agent import Agent

    agent = Agent(cfg)
    if args.command == "once":
        try:
            agent.run_once()
        finally:
            agent.close()
        return 0
    agent.run_forever()
    return 0


def _config_exists(path: str) -> bool:
    from pathlib import Path

    return Path(path).exists()


if __name__ == "__main__":
    sys.exit(main())
