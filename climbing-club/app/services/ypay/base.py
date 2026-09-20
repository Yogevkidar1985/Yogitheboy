from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class IssueResult:
    ok: bool
    external_id: str = ""
    receipt_number: str = ""
    pdf_url: str = ""
    sent_email: bool = False
    error: str = ""
    raw: dict = field(default_factory=dict)


class ReceiptProvider:
    name = "base"
    supports_email = False
    requires_manual_number = False

    def issue(self, data: dict, idempotency_key: str) -> IssueResult:  # pragma: no cover - interface
        raise NotImplementedError

    def send_email(self, external_id: str, email: str) -> IssueResult:  # pragma: no cover - interface
        return IssueResult(ok=False, error="הספק אינו תומך בשליחת מייל")
