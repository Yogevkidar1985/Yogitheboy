from __future__ import annotations

import logging

from ..models import Match
from .base import Notifier, format_match

log = logging.getLogger(__name__)


class ConsoleNotifier(Notifier):
    def notify(self, match: Match) -> None:
        print("\n" + format_match(match) + "\n", flush=True)

    def send_text(self, text: str) -> None:
        print(text, flush=True)
