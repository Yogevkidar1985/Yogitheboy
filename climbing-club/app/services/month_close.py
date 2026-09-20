"""מסך סגירת חודש: רשימת בדיקות, נתוני סיכום, סגירה ופתיחה מחדש."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from .. import audit
from ..models import (
    ChargeStatus,
    ClubSession,
    MessageStatus,
    MonthClosure,
    MonthlyCharge,
    Payment,
    Receipt,
    ReceiptStatus,
    SessionStatus,
    User,
)
from . import settings as settings_svc
from .attendance import missing_reports
from .billing import active_children_for_month, q2
from .calendar import month_range, month_sessions, past_sessions_needing_action
from .payments import unallocated_payments, unassigned_payments


@dataclass
class CheckItem:
    key: str
    label: str
    ok: bool
    detail: str
    link: str
    blocking: bool = True


@dataclass
class MonthSummary:
    year: int
    month: int
    active_children: int
    planned: int
    held: int
    cancelled: int
    moved: int
    missing_attendance: list
    total_charges: float
    total_paid: float
    open_balance: float
    messages_pending: int
    receipts_pending: int
    receipts_not_sent: int
    unassigned_payments: int
    unallocated_payments: int
    checks: list[CheckItem]
    closure: MonthClosure | None

    @property
    def done(self) -> int:
        return sum(1 for c in self.checks if c.ok)

    @property
    def can_close(self) -> bool:
        return all(c.ok for c in self.checks if c.blocking)


def summary(db: Session, year: int, month: int) -> MonthSummary:
    first, last = month_range(year, month)
    sessions = month_sessions(db, year, month)
    held = [s for s in sessions if s.status.counts_as_held]
    cancelled = [s for s in sessions if s.status.is_cancelled]
    moved = [s for s in sessions if s.status == SessionStatus.MOVED]
    missing = []
    for s in held:
        kids = missing_reports(db, s)
        if kids:
            missing.append((s, kids))
    stale = [s for s in past_sessions_needing_action(db) if first <= s.date <= last]
    charges = db.query(MonthlyCharge).filter_by(year=year, month=month).all()
    total = q2(sum(float(c.amount) for c in charges))
    paid = q2(sum(c.paid for c in charges))
    receipts_m = [
        r
        for r in db.query(Receipt).join(Payment).filter(Payment.paid_on >= first).all()
        if r.charge and (r.charge.year, r.charge.month) == (year, month)
    ]
    receipts_pending = [r for r in receipts_m if r.status in (ReceiptStatus.DRAFT, ReceiptStatus.APPROVED, ReceiptStatus.FAILED)]
    receipts_not_sent = [r for r in receipts_m if r.status == ReceiptStatus.ISSUED]
    msgs_pending = [c for c in charges if c.message is None or c.message.status != MessageStatus.SENT]
    unassigned = unassigned_payments(db)
    unalloc = unallocated_payments(db)
    active = active_children_for_month(db, year, month)
    closure = db.query(MonthClosure).filter_by(year=year, month=month).first()
    block_attendance = settings_svc.get(db, "block_close_on_missing_attendance") == "1"

    planned_left = [s for s in sessions if s.status == SessionStatus.PLANNED]
    checks = [
        CheckItem(
            "sessions",
            "כל המפגשים בחודש עודכנו (התקיים / בוטל / הועבר)",
            not planned_left and not stale,
            f"{len(planned_left)} מפגשים עדיין במצב 'מתוכנן'" if planned_left else "כל המפגשים עודכנו",
            f"/calendar?year={year}&month={month}",
        ),
        CheckItem(
            "attendance",
            "הנוכחות הושלמה לכל המפגשים",
            not missing,
            f"{sum(len(k) for _, k in missing)} דיווחים חסרים ב-{len(missing)} מפגשים" if missing else "הושלמה",
            f"/attendance?year={year}&month={month}",
            blocking=block_attendance,
        ),
        CheckItem(
            "charges",
            "החיובים חושבו ואושרו לכל הילדים הפעילים",
            bool(charges) and len(charges) >= len(active) and all(c.status != ChargeStatus.DRAFT for c in charges),
            f"{sum(1 for c in charges if c.status == ChargeStatus.DRAFT)} חיובים בטיוטה, {max(0, len(active) - len(charges))} טרם חושבו",
            f"/billing?year={year}&month={month}",
        ),
        CheckItem(
            "messages",
            "הודעות התשלום אושרו ונשלחו",
            bool(charges) and not msgs_pending,
            f"{len(msgs_pending)} הודעות טרם נשלחו" if msgs_pending else "כל ההודעות נשלחו",
            f"/billing/messages/list?year={year}&month={month}",
            blocking=False,
        ),
        CheckItem(
            "payments",
            "התשלומים נקלטו ושויכו",
            not unassigned and not unalloc,
            f"{len(unassigned)} תשלומים ללא ילד, {len(unalloc)} עם יתרה לא משויכת",
            "/payments",
            blocking=False,
        ),
        CheckItem(
            "receipts",
            "הקבלות אושרו והופקו",
            not receipts_pending,
            f"{len(receipts_pending)} קבלות ממתינות" if receipts_pending else "אין קבלות ממתינות",
            "/receipts",
            blocking=False,
        ),
    ]
    return MonthSummary(
        year=year,
        month=month,
        active_children=len(active),
        planned=len(sessions) - len(moved),
        held=len(held),
        cancelled=len(cancelled),
        moved=len(moved),
        missing_attendance=missing,
        total_charges=total,
        total_paid=paid,
        open_balance=q2(total - paid),
        messages_pending=len(msgs_pending),
        receipts_pending=len(receipts_pending),
        receipts_not_sent=len(receipts_not_sent),
        unassigned_payments=len(unassigned),
        unallocated_payments=len(unalloc),
        checks=checks,
        closure=closure,
    )


def close_month(db: Session, year: int, month: int, user: User | None, force: bool = False) -> MonthClosure:
    s = summary(db, year, month)
    if not s.can_close and not force:
        raise ValueError("לא ניתן לסגור את החודש: יש שלבי בדיקה חוסמים שלא הושלמו")
    mc = s.closure or MonthClosure(year=year, month=month)
    if mc.is_closed:
        raise ValueError("החודש כבר סגור")
    mc.closed_at = datetime.now()
    mc.closed_by = user.display_name if user else ""
    mc.reopened_at = None
    db.add(mc)
    for ch in db.query(MonthlyCharge).filter_by(year=year, month=month).all():
        ch.status = ChargeStatus.CLOSED
    db.flush()
    audit.log(db, user, "month_closure", mc.id, "close", after=audit.snapshot(mc), note="בכפייה" if force and not s.can_close else "")
    return mc


def reopen_month(db: Session, year: int, month: int, user: User | None, reason: str) -> MonthClosure:
    mc = db.query(MonthClosure).filter_by(year=year, month=month).first()
    if not mc or not mc.is_closed:
        raise ValueError("החודש אינו סגור")
    before = audit.snapshot(mc)
    mc.reopened_at = datetime.now()
    mc.notes = (mc.notes + "\n" if mc.notes else "") + f"נפתח מחדש: {reason}"
    for ch in db.query(MonthlyCharge).filter_by(year=year, month=month).all():
        ch.status = ChargeStatus.APPROVED
    audit.log(db, user, "month_closure", mc.id, "reopen", before=before, after=audit.snapshot(mc), note=reason)
    return mc
