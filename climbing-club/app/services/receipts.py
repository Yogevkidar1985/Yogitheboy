"""הכנת קבלות מתוך תשלום שנקלט, תצוגה מקדימה, אישור מפורש, הפקה דרך הספק ושליחה.

עקרונות:
* קבלה נוצרת רק מתשלום שנקלט ושויך (לא על סכום שלא התקבל).
* מפתח אידמפוטנטיות ייחודי לכל קבלה מונע הפקה כפולה גם בלחיצה חוזרת או בכשל תקשורת.
* הפקה מתבצעת רק לאחר אישור מפורש (סטטוס approved) ובלחיצה נפרדת.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from .. import audit
from ..models import (
    AttendanceStatus,
    Child,
    IntroSession,
    Payment,
    PaymentAllocation,
    Receipt,
    ReceiptKind,
    ReceiptMode,
    ReceiptStatus,
    User,
)
from . import settings as settings_svc
from .billing import q2
from .calendar import MONTH_NAMES
from .payments import METHOD_LABELS
from .ypay import get_provider

KIND_LABELS = {
    ReceiptKind.MONTHLY: "קבלה חודשית מרוכזת",
    ReceiptKind.PER_SESSION: "קבלה למפגש בודד",
    ReceiptKind.INTRO: "קבלה למפגש היכרות",
}
STATUS_LABELS = {
    ReceiptStatus.DRAFT: "ממתינה לבדיקה",
    ReceiptStatus.APPROVED: "אושרה להפקה",
    ReceiptStatus.ISSUED: "הופקה",
    ReceiptStatus.SENT: "נשלחה",
    ReceiptStatus.FAILED: "נכשלה",
    ReceiptStatus.CANCELLED: "בוטלה",
}


def _fmt_date(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _base_data(child: Child | None, payment: Payment) -> tuple[dict, list[str]]:
    contact = child.billing_contact if child else None
    payer = payment.payer_name or (contact.full_name if contact else "")
    email = contact.email if contact else ""
    missing: list[str] = []
    if not payer:
        missing.append("שם המשלם")
    if not email:
        missing.append("כתובת מייל לשליחה")
    required = [f.strip() for f in (child.receipt_required_fields if child else "").split(",") if f.strip()]
    data = {
        "payer_name": payer,
        "payer_id": contact.national_id if contact else "",
        "email": email,
        "child_name": child.full_name if child else "",
        "child_id_number": child.national_id if child else "",
        "hmo": child.hmo if child else "",
        "paid_on": payment.paid_on.isoformat(),
        "paid_on_display": _fmt_date(payment.paid_on),
        "method": payment.method.value,
        "method_display": METHOD_LABELS.get(payment.method.value, payment.method.value),
        "reference": payment.reference,
        "club_name": "",
        "footer": "",
    }
    for f in required:
        key = {"תעודת זהות": "child_id_number", "קופת חולים": "hmo", "מייל": "email", "ת.ז. משלם": "payer_id"}.get(f, f)
        if not data.get(key):
            missing.append(f)
    return data, missing


def _existing(db: Session, key: str) -> Receipt | None:
    return db.query(Receipt).filter_by(idempotency_key=key).first()


def prepare_for_payment(db: Session, payment: Payment, user: User | None) -> list[Receipt]:
    """בונה טיוטות קבלה לכל השיוכים של התשלום, לפי הגדרת הקבלה של הילד. לא יוצר כפילויות."""
    if payment.child is None:
        raise ValueError("יש לשייך את התשלום לילד לפני הכנת קבלה")
    child = payment.child
    created: list[Receipt] = []
    intro = db.query(IntroSession).filter_by(payment_id=payment.id).first()
    if intro:
        r = _prepare_intro(db, intro, payment, user)
        return [r] if r else []
    if not payment.allocations:
        raise ValueError("התשלום טרם שויך לחיוב חודשי – יש לשייך אותו קודם")
    for alloc in payment.allocations:
        child = alloc.charge.child  # שיוך לחיוב של אח – הקבלה על שם אותו ילד
        if child.receipt_mode == ReceiptMode.PER_SESSION:
            created += _prepare_per_session(db, child, payment, alloc, user)
        else:
            r = _prepare_monthly(db, child, payment, alloc, user)
            if r:
                created.append(r)
    db.flush()
    return created


def _sessions_of_charge(alloc: PaymentAllocation, only_charged: bool = True) -> list[dict]:
    lines = (alloc.charge.detail or {}).get("lines", [])
    out = []
    for l in lines:
        if l.get("session_status") in ("held", "pending_attendance"):
            if not only_charged or l.get("charged") or alloc.charge.method.value in ("fixed_monthly", "custom"):
                out.append(l)
    return out


def _prepare_monthly(db: Session, child: Child, payment: Payment, alloc: PaymentAllocation, user: User | None) -> Receipt | None:
    key = f"pay{payment.id}-charge{alloc.charge_id}-monthly"
    if _existing(db, key):
        return None
    data, missing = _base_data(child, payment)
    ch = alloc.charge
    sessions = _sessions_of_charge(alloc)
    dates = ", ".join(_fmt_date(date.fromisoformat(l["date"])) for l in sessions)
    ctx = {
        "child_name": child.full_name,
        "month_name": MONTH_NAMES[ch.month],
        "year": ch.year,
        "session_dates": dates or "—",
        "sessions_count": len(sessions),
    }
    description = settings_svc.get(db, "receipt_description_monthly").format(**ctx)
    data.update(
        {
            "amount": q2(alloc.amount),
            "description": description,
            "notes": child.receipt_notes,
            "club_name": settings_svc.get(db, "club_name"),
            "footer": settings_svc.get(db, "receipt_footer"),
            "lines": [{"description": description, "amount": q2(alloc.amount), "quantity": 1}],
            "session_dates": [l["date"] for l in sessions],
        }
    )
    if child.hmo:
        data["notes"] = (data["notes"] + "\n" if data["notes"] else "") + f"קופת חולים / גורם מממן: {child.hmo}"
    r = Receipt(
        idempotency_key=key,
        kind=ReceiptKind.MONTHLY,
        child_id=child.id,
        payment_id=payment.id,
        charge_id=ch.id,
        amount=q2(alloc.amount),
        payer_name=data["payer_name"],
        email=data["email"],
        description=description,
        notes=data["notes"],
        data=data,
        missing_fields=missing,
    )
    db.add(r)
    db.flush()
    audit.log(db, user, "receipt", r.id, "prepare", after=audit.snapshot(r))
    return r


def _prepare_per_session(db: Session, child: Child, payment: Payment, alloc: PaymentAllocation, user: User | None) -> list[Receipt]:
    """קבלה נפרדת לכל מפגש שחויב בחודש (למשל לביא). הסכום המשויך מתחלק לפי מחיר המפגשים."""
    ch = alloc.charge
    sessions = [l for l in _sessions_of_charge(alloc) if l.get("charged")]
    if not sessions:
        # תשלום חודשי קבוע עם קבלה לכל מפגש: מחלקים שווה בין המפגשים שהתקיימו
        sessions = _sessions_of_charge(alloc, only_charged=False)
    out: list[Receipt] = []
    if not sessions:
        return out
    total_price = sum(Decimal(str(l["price"])) for l in sessions)
    allocated = Decimal(str(alloc.amount))
    remaining = allocated
    for i, l in enumerate(sessions):
        key = f"pay{payment.id}-charge{ch.id}-session{l['session_id']}"
        if _existing(db, key):
            continue
        if i == len(sessions) - 1:
            amount = remaining
        elif total_price > 0:
            amount = (allocated * Decimal(str(l["price"])) / total_price).quantize(Decimal("0.01"))
        else:
            amount = (allocated / len(sessions)).quantize(Decimal("0.01"))
        remaining -= amount
        if amount <= 0:
            continue
        data, missing = _base_data(child, payment)
        sd = date.fromisoformat(l["date"])
        description = settings_svc.get(db, "receipt_description_session").format(
            child_name=child.full_name, session_date=_fmt_date(sd), month_name=MONTH_NAMES[sd.month], year=sd.year
        )
        data.update(
            {
                "amount": q2(amount),
                "description": description,
                "notes": child.receipt_notes,
                "club_name": settings_svc.get(db, "club_name"),
                "footer": settings_svc.get(db, "receipt_footer"),
                "lines": [{"description": description, "amount": q2(amount), "quantity": 1}],
                "session_dates": [l["date"]],
            }
        )
        if child.hmo:
            data["notes"] = (data["notes"] + "\n" if data["notes"] else "") + f"קופת חולים / גורם מממן: {child.hmo}"
        r = Receipt(
            idempotency_key=key,
            kind=ReceiptKind.PER_SESSION,
            child_id=child.id,
            payment_id=payment.id,
            charge_id=ch.id,
            session_id=l["session_id"],
            amount=q2(amount),
            payer_name=data["payer_name"],
            email=data["email"],
            description=description,
            notes=data["notes"],
            data=data,
            missing_fields=missing,
        )
        db.add(r)
        db.flush()
        audit.log(db, user, "receipt", r.id, "prepare", after=audit.snapshot(r))
        out.append(r)
    return out


def _prepare_intro(db: Session, intro: IntroSession, payment: Payment, user: User | None) -> Receipt | None:
    key = f"pay{payment.id}-intro{intro.id}"
    if _existing(db, key):
        return None
    child = intro.child
    data, missing = _base_data(child, payment)
    description = settings_svc.get(db, "receipt_description_intro").format(
        child_name=child.full_name, session_date=_fmt_date(intro.session.date)
    )
    data.update(
        {
            "amount": q2(payment.amount),
            "description": description,
            "notes": child.receipt_notes,
            "club_name": settings_svc.get(db, "club_name"),
            "footer": settings_svc.get(db, "receipt_footer"),
            "lines": [{"description": description, "amount": q2(payment.amount), "quantity": 1}],
            "session_dates": [intro.session.date.isoformat()],
        }
    )
    r = Receipt(
        idempotency_key=key,
        kind=ReceiptKind.INTRO,
        child_id=child.id,
        payment_id=payment.id,
        session_id=intro.session_id,
        amount=q2(payment.amount),
        payer_name=data["payer_name"],
        email=data["email"],
        description=description,
        notes=data["notes"],
        data=data,
        missing_fields=missing,
    )
    db.add(r)
    db.flush()
    audit.log(db, user, "receipt", r.id, "prepare", after=audit.snapshot(r))
    return r


def update_draft(db: Session, r: Receipt, user: User | None, **fields) -> None:
    if r.status not in (ReceiptStatus.DRAFT, ReceiptStatus.APPROVED, ReceiptStatus.FAILED):
        raise ValueError("לא ניתן לערוך קבלה שכבר הופקה")
    before = audit.snapshot(r)
    data = dict(r.data or {})
    for k, v in fields.items():
        if v is None:
            continue
        setattr(r, k, v)
        data[k] = v
    r.data = data
    r.missing_fields = [m for m in (r.missing_fields or []) if not ((m == "שם המשלם" and r.payer_name) or (m == "כתובת מייל לשליחה" and r.email))]
    if r.status == ReceiptStatus.APPROVED:
        r.status = ReceiptStatus.DRAFT  # עריכה אחרי אישור מחייבת אישור מחדש
    audit.log(db, user, "receipt", r.id, "edit", before=before, after=audit.snapshot(r))


def approve(db: Session, r: Receipt, user: User | None) -> None:
    if r.status not in (ReceiptStatus.DRAFT, ReceiptStatus.FAILED):
        raise ValueError("הקבלה אינה במצב המאפשר אישור")
    if r.missing_fields:
        raise ValueError("חסרים שדות חובה: " + ", ".join(r.missing_fields))
    if q2(r.amount) <= 0:
        raise ValueError("סכום הקבלה חייב להיות חיובי")
    before = audit.snapshot(r)
    r.status = ReceiptStatus.APPROVED
    r.approved_by = user.display_name if user else ""
    r.approved_at = datetime.now()
    audit.log(db, user, "receipt", r.id, "approve", before=before, after=audit.snapshot(r))


def issue(db: Session, r: Receipt, user: User | None, manual_number: str = "") -> Receipt:
    """הפקה בפועל דרך הספק. מוגן מפני הפקה כפולה."""
    if r.status in (ReceiptStatus.ISSUED, ReceiptStatus.SENT):
        raise ValueError("הקבלה כבר הופקה – לא ניתן להפיק שוב")
    if r.status != ReceiptStatus.APPROVED:
        raise ValueError("יש לאשר את הקבלה לפני ההפקה")
    provider = get_provider()
    before = audit.snapshot(r)
    data = dict(r.data or {})
    data["amount"] = q2(r.amount)
    data["payer_name"] = r.payer_name
    data["email"] = r.email
    data["description"] = r.description
    data["notes"] = r.notes
    if manual_number:
        data["manual_receipt_number"] = manual_number
    res = provider.issue(data, r.idempotency_key)
    r.provider = provider.name
    if res.ok:
        r.status = ReceiptStatus.ISSUED
        r.external_id = res.external_id
        r.receipt_number = res.receipt_number
        r.pdf_url = res.pdf_url
        r.error = ""
        r.issued_at = datetime.now()
    else:
        r.status = ReceiptStatus.FAILED
        r.error = res.error
    audit.log(db, user, "receipt", r.id, "issue", before=before, after=audit.snapshot(r), note=res.error)
    return r


def send(db: Session, r: Receipt, user: User | None) -> Receipt:
    if r.status != ReceiptStatus.ISSUED:
        raise ValueError("ניתן לשלוח רק קבלה שהופקה בהצלחה")
    if not r.email:
        raise ValueError("חסרה כתובת מייל")
    provider = get_provider()
    before = audit.snapshot(r)
    if not provider.supports_email:
        raise ValueError("הספק הנוכחי אינו שולח מייל – יש לשלוח את הקבלה ידנית ולסמן כנשלחה")
    res = provider.send_email(r.external_id, r.email)
    if res.ok:
        r.status = ReceiptStatus.SENT
        r.sent_at = datetime.now()
        r.error = ""
    else:
        r.error = res.error
    audit.log(db, user, "receipt", r.id, "send", before=before, after=audit.snapshot(r), note=res.error)
    return r


def mark_sent_manually(db: Session, r: Receipt, user: User | None) -> None:
    if r.status != ReceiptStatus.ISSUED:
        raise ValueError("ניתן לסמן כנשלחה רק קבלה שהופקה")
    before = audit.snapshot(r)
    r.status = ReceiptStatus.SENT
    r.sent_at = datetime.now()
    audit.log(db, user, "receipt", r.id, "mark_sent", before=before, after=audit.snapshot(r))


def cancel(db: Session, r: Receipt, user: User | None, reason: str) -> None:
    if r.status in (ReceiptStatus.ISSUED, ReceiptStatus.SENT):
        raise ValueError("קבלה שהופקה מבוטלת רק דרך YPAY / הנהלת החשבונות, לא מהמערכת")
    before = audit.snapshot(r)
    r.status = ReceiptStatus.CANCELLED
    r.error = reason
    audit.log(db, user, "receipt", r.id, "cancel", before=before, after=audit.snapshot(r), note=reason)


def pending(db: Session) -> list[Receipt]:
    return (
        db.query(Receipt)
        .filter(Receipt.status.in_([ReceiptStatus.DRAFT, ReceiptStatus.APPROVED, ReceiptStatus.FAILED]))
        .order_by(Receipt.created_at)
        .all()
    )
