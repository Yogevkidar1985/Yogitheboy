"""הודעות תשלום להורים – יצירה מתבנית, עריכה, אישור וסימון כנשלח."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from .. import audit
from ..models import MessageStatus, MonthlyCharge, PaymentMessage, User
from . import settings as settings_svc
from .billing import previous_balance, q2
from .calendar import MONTH_NAMES


def fmt_money(x) -> str:
    x = q2(x)
    return f"{int(x):,}" if x == int(x) else f"{x:,.2f}"


def render(db: Session, ch: MonthlyCharge, template: str | None = None) -> str:
    child = ch.child
    contact = child.message_contact
    prev = previous_balance(db, child, ch.year, ch.month)
    ctx = {
        "parent_name": contact.full_name if contact else "",
        "child_name": child.full_name,
        "month_name": MONTH_NAMES[ch.month],
        "year": ch.year,
        "sessions_held": ch.sessions_held,
        "sessions_attended": ch.sessions_attended,
        "sessions_absent": ch.sessions_absent,
        "sessions_cancelled": ch.sessions_cancelled,
        "amount": fmt_money(ch.amount),
        "total_due": fmt_money(q2(ch.amount) + prev),
        "previous_balance": fmt_money(prev),
        "previous_balance_line": (f"יתרת חוב קודמת: {fmt_money(prev)} ₪\n" if prev > 0 else ""),
        "signature": settings_svc.get(db, "signature"),
        "club_name": settings_svc.get(db, "club_name"),
    }
    tpl = template if template is not None else settings_svc.get(db, "message_template")
    try:
        return tpl.format(**ctx)
    except (KeyError, IndexError, ValueError) as e:  # תבנית עם שדה לא מוכר
        return tpl + f"\n\n[שגיאה בתבנית: {e}]"


def ensure_message(db: Session, ch: MonthlyCharge, user: User | None, regenerate: bool = False) -> PaymentMessage:
    msg = ch.message
    contact = ch.child.message_contact
    if msg is None:
        msg = PaymentMessage(charge_id=ch.id)
        db.add(msg)
        regenerate = True
    if regenerate and msg.status != MessageStatus.SENT:
        msg.body = render(db, ch)
        msg.recipient_name = contact.full_name if contact else ""
        msg.recipient_phone = contact.phone if contact else ""
        msg.status = MessageStatus.DRAFT
    db.flush()
    return msg


def approve(db: Session, msg: PaymentMessage, user: User | None, body: str | None = None) -> None:
    before = audit.snapshot(msg)
    if body is not None:
        msg.body = body
    msg.status = MessageStatus.APPROVED
    msg.approved_at = datetime.now()
    audit.log(db, user, "payment_message", msg.id, "approve", before=before, after=audit.snapshot(msg))


def mark_sent(db: Session, msg: PaymentMessage, user: User | None) -> None:
    if msg.status == MessageStatus.SENT:
        raise ValueError("ההודעה כבר סומנה כנשלחה – מניעת שליחה כפולה")
    before = audit.snapshot(msg)
    msg.status = MessageStatus.SENT
    msg.sent_at = datetime.now()
    msg.sent_by = user.display_name if user else ""
    audit.log(db, user, "payment_message", msg.id, "sent", before=before, after=audit.snapshot(msg))


def whatsapp_link(phone: str, body: str) -> str:
    """קישור wa.me פותח את וואטסאפ עם ההודעה מוכנה; השליחה עצמה ידנית (שלב 1)."""
    from urllib.parse import quote

    digits = "".join(ch for ch in phone if ch.isdigit())
    if digits.startswith("0"):
        digits = "972" + digits[1:]
    return f"https://wa.me/{digits}?text={quote(body)}" if digits else f"https://wa.me/?text={quote(body)}"
