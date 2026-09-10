from __future__ import annotations

from .base import Notifier
from .console import ConsoleNotifier
from .telegram import TelegramNotifier


def build_notifiers(cfg) -> list[Notifier]:
    notifiers: list[Notifier] = []
    if cfg.telegram.enabled:
        notifiers.append(TelegramNotifier(cfg.telegram.bot_token, cfg.telegram.chat_id))
    if cfg.notify_console or not notifiers:
        notifiers.append(ConsoleNotifier())
    return notifiers
