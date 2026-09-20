"""מסלול חצי-אוטומטי: המערכת מכינה את כל נתוני הקבלה, המשתמשת מפיקה באתר YPAY ומזינה את מספר הקבלה."""
from __future__ import annotations

from .base import IssueResult, ReceiptProvider


class ManualProvider(ReceiptProvider):
    name = "manual"
    supports_email = False
    requires_manual_number = True

    def issue(self, data: dict, idempotency_key: str) -> IssueResult:
        number = (data.get("manual_receipt_number") or "").strip()
        if not number:
            return IssueResult(ok=False, error="יש להזין את מספר הקבלה כפי שהופקה ב-YPAY")
        return IssueResult(ok=True, external_id=f"MANUAL-{number}", receipt_number=number)
