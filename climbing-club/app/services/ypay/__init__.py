"""ספקי הפקת קבלות. הבחירה לפי CLUB_RECEIPT_PROVIDER."""
from __future__ import annotations

from ... import config
from .base import IssueResult, ReceiptProvider


def get_provider() -> ReceiptProvider:
    name = config.RECEIPT_PROVIDER
    if name == "ypay_api":
        from .ypay_api import YPayApiProvider

        return YPayApiProvider()
    if name == "manual":
        from .manual import ManualProvider

        return ManualProvider()
    from .mock import MockProvider

    return MockProvider()


__all__ = ["get_provider", "IssueResult", "ReceiptProvider"]
