from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

from .models import SearchSpec


@dataclass
class TelegramConfig:
    bot_token: str = ""
    chat_id: str = ""

    @property
    def enabled(self) -> bool:
        return bool(self.bot_token and self.chat_id)


@dataclass
class FacebookConfig:
    state_file: str = "fb_state.json"  # Playwright storage state (cookies) after login
    city_slug: str = "telaviv"  # part of the marketplace URL, e.g. facebook.com/marketplace/telaviv
    headless: bool = True
    max_results: int = 40


@dataclass
class Config:
    searches: list[SearchSpec] = field(default_factory=list)
    interval_seconds: int = 300
    jitter_seconds: int = 60
    db_path: str = "data/seen.db"
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    facebook: FacebookConfig = field(default_factory=FacebookConfig)
    notify_console: bool = True


def _spec_from_dict(d: dict) -> SearchSpec:
    return SearchSpec(
        name=str(d.get("name") or d.get("query")),
        query=str(d["query"]),
        max_price=_num(d.get("max_price")),
        min_price=_num(d.get("min_price")),
        must_include=_strlist(d.get("must_include")),
        any_of=_strlist(d.get("any_of")),
        exclude=_strlist(d.get("exclude")),
        sources=_strlist(d.get("sources")) or ["yad2"],
        location=str(d.get("location") or ""),
        allow_no_price=bool(d.get("allow_no_price", False)),
        yad2_category=str(d.get("yad2_category") or ""),
    )


def _num(v):
    if v is None or v == "":
        return None
    return float(v)


def _strlist(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [v]
    return [str(x) for x in v]


def load_config(path: str | Path = "config.yaml") -> Config:
    """Load config.yaml and merge secrets from environment / .env file."""
    load_dotenv()
    path = Path(path)
    raw: dict = {}
    if path.exists():
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    fb_raw = raw.get("facebook") or {}
    cfg = Config(
        searches=[_spec_from_dict(s) for s in raw.get("searches", [])],
        interval_seconds=int(raw.get("interval_seconds", 300)),
        jitter_seconds=int(raw.get("jitter_seconds", 60)),
        db_path=str(raw.get("db_path", "data/seen.db")),
        notify_console=bool(raw.get("notify_console", True)),
        telegram=TelegramConfig(
            bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        ),
        facebook=FacebookConfig(
            state_file=str(fb_raw.get("state_file", os.getenv("FB_STATE_FILE", "fb_state.json"))),
            city_slug=str(fb_raw.get("city_slug", "telaviv")),
            headless=bool(fb_raw.get("headless", True)),
            max_results=int(fb_raw.get("max_results", 40)),
        ),
    )
    if not cfg.searches:
        raise SystemExit(
            f"No searches defined. Copy config.example.yaml to {path} and add what you're looking for."
        )
    return cfg
