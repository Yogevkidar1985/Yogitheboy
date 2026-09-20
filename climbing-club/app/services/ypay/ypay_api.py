"""חיבור API ל-YPAY.

חשוב: מבנה ה-API של YPAY טרם אומת מול תיעוד רשמי (ראו docs/05-ypay-integration.md).
המחלקה בנויה כך שרק פונקציות ה-payload והפענוח יצטרכו להתאמה לאחר קבלת התיעוד.
"""
from __future__ import annotations

import httpx

from ... import config
from .base import IssueResult, ReceiptProvider


class YPayApiProvider(ReceiptProvider):
    name = "ypay_api"
    supports_email = True

    def __init__(self) -> None:
        if not config.YPAY_API_BASE_URL or not config.YPAY_API_KEY:
            raise RuntimeError("חסרים YPAY_API_BASE_URL / YPAY_API_KEY בסביבה")
        self.client = httpx.Client(
            base_url=config.YPAY_API_BASE_URL,
            headers={"Authorization": f"Bearer {config.YPAY_API_KEY}", "Accept": "application/json"},
            timeout=30,
        )

    # ---- להתאמה לפי תיעוד YPAY
    def _build_payload(self, data: dict, idempotency_key: str) -> dict:
        return {
            "idempotency_key": idempotency_key,
            "customer": {
                "name": data.get("payer_name"),
                "email": data.get("email"),
                "id_number": data.get("payer_id", ""),
            },
            "date": data.get("paid_on"),
            "amount": data.get("amount"),
            "payment_method": data.get("method"),
            "reference": data.get("reference", ""),
            "description": data.get("description"),
            "notes": data.get("notes", ""),
            "lines": data.get("lines", []),
            "sandbox": config.YPAY_SANDBOX,
        }

    def _parse(self, body: dict) -> IssueResult:
        return IssueResult(
            ok=True,
            external_id=str(body.get("id", "")),
            receipt_number=str(body.get("number", body.get("receipt_number", ""))),
            pdf_url=body.get("pdf_url", body.get("url", "")),
            raw=body,
        )

    def issue(self, data: dict, idempotency_key: str) -> IssueResult:
        try:
            r = self.client.post(
                "/receipts",
                json=self._build_payload(data, idempotency_key),
                headers={"Idempotency-Key": idempotency_key},
            )
        except httpx.HTTPError as e:
            return IssueResult(ok=False, error=f"שגיאת תקשורת מול YPAY: {e}")
        if r.status_code >= 400:
            return IssueResult(ok=False, error=f"YPAY החזיר שגיאה {r.status_code}: {r.text[:300]}", raw={"status": r.status_code})
        try:
            return self._parse(r.json())
        except ValueError:
            return IssueResult(ok=False, error="תשובה לא צפויה מ-YPAY", raw={"text": r.text[:300]})

    def send_email(self, external_id: str, email: str) -> IssueResult:
        try:
            r = self.client.post(f"/receipts/{external_id}/send", json={"email": email})
        except httpx.HTTPError as e:
            return IssueResult(ok=False, error=f"שגיאת תקשורת מול YPAY: {e}")
        if r.status_code >= 400:
            return IssueResult(ok=False, error=f"שליחת המייל נכשלה ({r.status_code})")
        return IssueResult(ok=True, external_id=external_id, sent_email=True)
