"""Telegram bot notifier. Create a bot with @BotFather, then message it once
and read your chat id from https://api.telegram.org/bot<TOKEN>/getUpdates."""

from __future__ import annotations

import logging

import httpx

from ..models import Match
from .base import Notifier, format_match

log = logging.getLogger(__name__)


class TelegramNotifier(Notifier):
    def __init__(self, token: str, chat_id: str, client: httpx.Client | None = None):
        self.base = f"https://api.telegram.org/bot{token}"
        self.chat_id = chat_id
        self.client = client or httpx.Client(timeout=20)

    def send_text(self, text: str) -> None:
        try:
            r = self.client.post(
                f"{self.base}/sendMessage",
                json={"chat_id": self.chat_id, "text": text, "disable_web_page_preview": False},
            )
            if r.status_code != 200:
                log.error("telegram sendMessage failed: %s %s", r.status_code, r.text[:200])
        except httpx.HTTPError as e:
            log.error("telegram request failed: %s", e)

    def notify(self, match: Match) -> None:
        l = match.listing
        text = format_match(match)
        if l.image_url and l.image_url.startswith("http"):
            try:
                r = self.client.post(
                    f"{self.base}/sendPhoto",
                    json={"chat_id": self.chat_id, "photo": l.image_url, "caption": text[:1024]},
                )
                if r.status_code == 200:
                    return
                log.debug("telegram sendPhoto failed (%s), falling back to text", r.status_code)
            except httpx.HTTPError:
                pass
        self.send_text(text)
