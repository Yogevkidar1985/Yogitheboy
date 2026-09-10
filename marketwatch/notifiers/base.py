from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Match


class Notifier(ABC):
    @abstractmethod
    def notify(self, match: Match) -> None: ...

    def send_text(self, text: str) -> None:  # optional: plain messages (startup, errors)
        pass


def format_match(match: Match) -> str:
    """Human-readable alert text shared by all notifiers."""
    l, s = match.listing, match.spec
    head = "🔔 נמצא פריט חדש" if match.reason == "new" else "📉 ירידת מחיר"
    lines = [f"{head} — {s.name}", "", f"📦 {l.title}", f"💰 {l.price_text()}"]
    if match.reason == "price_drop" and match.previous_price is not None:
        lines[-1] += f" (היה ₪{match.previous_price:,.0f})"
    if l.location:
        lines.append(f"📍 {l.location}")
    lines.append(f"🌐 {l.source}")
    lines.append(l.url)
    return "\n".join(lines)
