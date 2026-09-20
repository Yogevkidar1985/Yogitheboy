"""ספק סימולציה: מדמה הפקה מוצלחת ומחזיר מספר קבלה מדומה. לשימוש בפיתוח ובבדיקות בלבד."""
from __future__ import annotations

import hashlib
import json

from .base import IssueResult, ReceiptProvider


class MockProvider(ReceiptProvider):
    name = "mock"
    supports_email = True

    def issue(self, data: dict, idempotency_key: str) -> IssueResult:
        digest = hashlib.sha1(idempotency_key.encode()).hexdigest()[:8].upper()
        return IssueResult(
            ok=True,
            external_id=f"MOCK-{digest}",
            receipt_number=f"SIM-{digest}",
            pdf_url="",
            raw={"simulated": True, "payload": json.loads(json.dumps(data, default=str))},
        )

    def send_email(self, external_id: str, email: str) -> IssueResult:
        return IssueResult(ok=True, external_id=external_id, sent_email=True, raw={"simulated": True, "to": email})
