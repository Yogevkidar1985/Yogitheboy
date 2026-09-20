"""קליטת תשלומים, בדיקת כפילויות ושיוך לחיובים."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from .. import audit
from ..models import ChargeStatus, Child, MonthlyCharge, Payment, PaymentAllocation, User
from .billing import q2

METHOD_LABELS = {
    "bank_transfer": "העברה בנקאית",
    "cash": "מזומן",
    "credit_card": "אשראי",
    "check": "צ'ק",
    "bit": "ביט",
    "paybox": "פייבוקס",
    "other": "אחר",
}


def find_duplicates(db: Session, amount: float, paid_on: date, reference: str = "", exclude_id: int | None = None) -> list[Payment]:
    """כפילות אפשרית: אותו סכום ואותו תאריך, או אותה אסמכתא."""
    q = db.query(Payment)
    if exclude_id:
        q = q.filter(Payment.id != exclude_id)
    out = []
    for p in q.all():
        same_ref = reference and p.reference and p.reference.strip() == reference.strip()
        same_amt_date = q2(p.amount) == q2(amount) and p.paid_on == paid_on
        if same_ref or same_amt_date:
            out.append(p)
    return out


def create_payment(db: Session, user: User | None, **fields) -> Payment:
    p = Payment(created_by=user.display_name if user else "", **fields)
    db.add(p)
    db.flush()
    audit.log(db, user, "payment", p.id, "create", after=audit.snapshot(p))
    return p


def open_charges_for_child(db: Session, child: Child) -> list[MonthlyCharge]:
    """חיובים עם יתרה פתוחה, מהישן לחדש."""
    chs = (
        db.query(MonthlyCharge)
        .filter(MonthlyCharge.child_id == child.id, MonthlyCharge.status != ChargeStatus.DRAFT)
        .order_by(MonthlyCharge.year, MonthlyCharge.month)
        .all()
    )
    return [c for c in chs if c.balance > 0.004]


def allocate(db: Session, payment: Payment, charge: MonthlyCharge, amount: float, user: User | None) -> PaymentAllocation:
    amount = q2(amount)
    if amount <= 0:
        raise ValueError("סכום השיוך חייב להיות חיובי")
    if amount > payment.unallocated + 0.004:
        raise ValueError("הסכום גדול מהיתרה הלא-משויכת של התשלום")
    a = PaymentAllocation(payment=payment, charge=charge, amount=amount)  # דרך הקשר, כדי ש-payment.unallocated יתעדכן מיד
    db.add(a)
    db.flush()
    audit.log(db, user, "payment_allocation", a.id, "create", after=audit.snapshot(a))
    return a


def auto_allocate(db: Session, payment: Payment, user: User | None) -> list[PaymentAllocation]:
    """שיוך אוטומטי של תשלום לחיובים הפתוחים של הילד, מהישן לחדש (תומך בתשלום חלקי ובכמה חודשים)."""
    if payment.child is None:
        return []
    out = []
    remaining = Decimal(str(payment.unallocated))
    for ch in open_charges_for_child(db, payment.child):
        if remaining <= 0:
            break
        take = min(remaining, Decimal(str(ch.balance)))
        if take > 0:
            out.append(allocate(db, payment, ch, float(take), user))
            remaining -= take
    return out


def remove_allocation(db: Session, alloc: PaymentAllocation, user: User | None) -> None:
    before = audit.snapshot(alloc)
    db.delete(alloc)
    audit.log(db, user, "payment_allocation", before["id"], "delete", before=before)


def unassigned_payments(db: Session) -> list[Payment]:
    return db.query(Payment).filter(Payment.child_id.is_(None)).order_by(Payment.paid_on.desc()).all()


def unallocated_payments(db: Session) -> list[Payment]:
    return [p for p in db.query(Payment).filter(Payment.child_id.isnot(None)).all() if p.unallocated > 0.004]
