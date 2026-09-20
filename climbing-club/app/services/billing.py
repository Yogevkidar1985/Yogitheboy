"""מנוע חישוב החיוב החודשי.

לכל ילד: המפגשים שהתקיימו בקבוצות שלו בחודש, הנוכחות בפועל, כלל החיוב האישי (עם היסטוריה),
חריגים ברמת מפגש, זיכויים והתאמות. התוצאה נשמרת ב-MonthlyCharge כתמונת מצב.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from .. import audit
from ..models import (
    Adjustment,
    Attendance,
    AttendanceStatus,
    BillingMethod,
    BillingRule,
    ChargeOverride,
    ChargeStatus,
    Child,
    ChildStatus,
    ClubSession,
    MonthClosure,
    MonthlyCharge,
    SessionKind,
    User,
)
from . import settings as settings_svc
from .calendar import month_range, month_sessions

METHOD_LABELS = {
    BillingMethod.PER_ATTENDANCE: "חיוב לפי נוכחות",
    BillingMethod.PER_HELD_SESSION: "חיוב לפי מפגשים שהתקיימו",
    BillingMethod.FIXED_MONTHLY: "חיוב חודשי קבוע",
    BillingMethod.CUSTOM: "הסדר אישי",
}


def q2(x) -> float:
    return float(Decimal(str(x or 0)).quantize(Decimal("0.01")))


@dataclass
class SessionLine:
    session_id: int
    date: str
    group: str
    session_status: str
    attendance: str  # present/absent/unreported/-
    charged: bool
    price: float
    note: str = ""


@dataclass
class ChargeResult:
    child_id: int
    year: int
    month: int
    method: BillingMethod
    rule: BillingRule | None
    sessions_held: int = 0
    sessions_attended: int = 0
    sessions_absent: int = 0
    sessions_unreported: int = 0
    sessions_cancelled: int = 0
    price_per_session: float = 0.0
    base_amount: float = 0.0
    adjustments_total: float = 0.0
    custom_amount: float | None = None
    amount: float = 0.0
    warnings: list[str] = field(default_factory=list)
    lines: list[SessionLine] = field(default_factory=list)
    adjustments: list[dict] = field(default_factory=list)


def rule_for(child: Child, on: date) -> BillingRule | None:
    return child.current_rule(on)


def child_sessions_in_month(db: Session, child: Child, year: int, month: int) -> list[ClubSession]:
    """כל המפגשים (כולל שבוטלו/הועברו) של הקבוצות שהילד חבר בהן במועד המפגש, וכן מפגשים שדווחה בהם נוכחות."""
    out: dict[int, ClubSession] = {}
    for s in month_sessions(db, year, month, kind=SessionKind.REGULAR):
        for m in child.memberships:
            if m.group_id == s.group_id and m.covers(s.date):
                out[s.id] = s
                break
    first, last = month_range(year, month)
    for a in child.attendance:
        if first <= a.session.date <= last and a.session.kind == SessionKind.REGULAR:
            out[a.session.id] = a.session
    return sorted(out.values(), key=lambda s: (s.date, s.group_id or 0))


def compute(db: Session, child: Child, year: int, month: int, custom_amount: float | None = None) -> ChargeResult:
    first, _ = month_range(year, month)
    rule = rule_for(child, first)
    method = rule.method if rule else BillingMethod.PER_ATTENDANCE
    res = ChargeResult(child_id=child.id, year=year, month=month, method=method, rule=rule)
    if rule is None:
        res.warnings.append("לא הוגדר כלל חיוב לילד – החישוב הוא 0 עד שיוגדר תעריף")
    res.price_per_session = q2(rule.price_per_session) if rule else 0.0

    att_by_session = {a.session_id: a for a in child.attendance}
    base = Decimal("0")
    for s in child_sessions_in_month(db, child, year, month):
        a = att_by_session.get(s.id)
        # תעריף לפי תאריך המפגש (היסטוריית תעריפים)
        srule = rule_for(child, s.date) or rule
        price = Decimal(str(a.price_override)) if (a and a.price_override is not None) else Decimal(str(srule.price_per_session if srule else 0))
        line = SessionLine(
            session_id=s.id,
            date=s.date.isoformat(),
            group=s.group.name if s.group else "",
            session_status=s.status.value,
            attendance=a.status.value if a else "-",
            charged=False,
            price=q2(price),
            note=(a.note if a else "") or "",
        )
        if s.status.is_cancelled or s.status.value == "moved":
            if s.status.is_cancelled:
                res.sessions_cancelled += 1
            res.lines.append(line)
            continue
        if not s.status.counts_as_held:
            # מתוכנן ועדיין לא התקיים – לא נספר
            line.note = "מתוכנן"
            res.lines.append(line)
            continue
        res.sessions_held += 1
        st = a.status if a else AttendanceStatus.UNREPORTED
        if st == AttendanceStatus.PRESENT:
            res.sessions_attended += 1
        elif st == AttendanceStatus.ABSENT:
            res.sessions_absent += 1
        else:
            res.sessions_unreported += 1

        override = a.charge_override if a else ChargeOverride.DEFAULT
        if override == ChargeOverride.CHARGE:
            charged = True
        elif override == ChargeOverride.NO_CHARGE:
            charged = False
        elif method == BillingMethod.PER_ATTENDANCE:
            charged = st == AttendanceStatus.PRESENT
        elif method == BillingMethod.PER_HELD_SESSION:
            charged = True
        else:
            charged = False  # חודשי קבוע / הסדר אישי – המפגש אינו מחויב בנפרד
        line.charged = charged
        if charged:
            base += price
        res.lines.append(line)

    if res.sessions_unreported:
        res.warnings.append(f"{res.sessions_unreported} מפגשים ללא דיווח נוכחות – יש להשלים לפני סגירת החודש")

    if method == BillingMethod.FIXED_MONTHLY:
        base = Decimal(str(rule.fixed_monthly_amount if rule else 0))
        policy = settings_svc.get(db, "cancel_policy_fixed_monthly")
        if res.sessions_cancelled:
            if policy == settings_svc.CANCEL_POLICY_CREDIT:
                base -= Decimal(str(res.price_per_session)) * res.sessions_cancelled
                res.warnings.append(f"הופחת זיכוי על {res.sessions_cancelled} מפגשים שבוטלו לפי מדיניות ההגדרות")
            elif policy == settings_svc.CANCEL_POLICY_UNSET:
                res.warnings.append(
                    "היו מפגשים שבוטלו והמדיניות לילדים בתשלום קבוע טרם הוגדרה בהגדרות – יש להחליט ולהוסיף זיכוי ידני במידת הצורך"
                )
        # מפגשים בעלי override מפורש 'לחייב' מתווספים לתשלום הקבוע (למשל מפגש נוסף)
        base += sum((Decimal(str(l.price)) for l in res.lines if l.charged), Decimal("0"))
    elif method == BillingMethod.CUSTOM:
        existing = db.query(MonthlyCharge).filter_by(child_id=child.id, year=year, month=month).first()
        if custom_amount is None and existing and existing.custom_amount is not None:
            custom_amount = float(existing.custom_amount)
        if custom_amount is None:
            res.warnings.append("הסדר אישי – יש להזין את הסכום החודשי ידנית" + (f" ({rule.description})" if rule and rule.description else ""))
            custom_amount = 0.0
        res.custom_amount = q2(custom_amount)
        base = Decimal(str(res.custom_amount)) + sum((Decimal(str(l.price)) for l in res.lines if l.charged), Decimal("0"))

    res.base_amount = q2(base)
    adjs = db.query(Adjustment).filter_by(child_id=child.id, year=year, month=month).all()
    res.adjustments = [
        {"id": a.id, "amount": q2(a.amount), "reason": a.reason, "session_id": a.session_id} for a in adjs
    ]
    res.adjustments_total = q2(sum(Decimal(str(a.amount)) for a in adjs))
    res.amount = q2(Decimal(str(res.base_amount)) + Decimal(str(res.adjustments_total)))
    if res.amount < 0:
        res.warnings.append("הסכום לחיוב שלילי – יש לבדוק את הזיכויים")
    return res


def is_month_closed(db: Session, year: int, month: int) -> bool:
    mc = db.query(MonthClosure).filter_by(year=year, month=month).first()
    return bool(mc and mc.is_closed)


def active_children_for_month(db: Session, year: int, month: int) -> list[Child]:
    """ילדים שהיו פעילים בחלק כלשהו מהחודש (לפי תאריכי הצטרפות/סיום) או שיש להם מפגשים בחודש."""
    first, last = month_range(year, month)
    out = []
    for c in db.query(Child).order_by(Child.full_name).all():
        if c.joined_on and c.joined_on > last:
            continue
        if c.left_on and c.left_on < first:
            continue
        if c.status == ChildStatus.LEFT and not c.left_on:
            continue
        if c.status == ChildStatus.PAUSED and not any(first <= a.session.date <= last for a in c.attendance):
            continue
        out.append(c)
    return out


def save_charge(db: Session, child: Child, year: int, month: int, user: User | None, custom_amount: float | None = None) -> MonthlyCharge:
    """מחשב ושומר (או מעדכן) את החיוב החודשי. חיוב סגור אינו משתנה."""
    existing = db.query(MonthlyCharge).filter_by(child_id=child.id, year=year, month=month).first()
    if existing and existing.status == ChargeStatus.CLOSED:
        return existing
    res = compute(db, child, year, month, custom_amount=custom_amount)
    before = audit.snapshot(existing) if existing else None
    ch = existing or MonthlyCharge(child_id=child.id, year=year, month=month, method=res.method)
    ch.method = res.method
    ch.sessions_held = res.sessions_held
    ch.sessions_attended = res.sessions_attended
    ch.sessions_absent = res.sessions_absent
    ch.sessions_unreported = res.sessions_unreported
    ch.sessions_cancelled = res.sessions_cancelled
    ch.price_per_session = res.price_per_session
    ch.base_amount = res.base_amount
    ch.adjustments_total = res.adjustments_total
    ch.custom_amount = res.custom_amount
    ch.amount = res.amount
    ch.warnings = res.warnings
    ch.detail = {
        "lines": [l.__dict__ for l in res.lines],
        "adjustments": res.adjustments,
        "rule": {
            "method": res.method.value,
            "price_per_session": res.price_per_session,
            "fixed_monthly_amount": q2(res.rule.fixed_monthly_amount) if res.rule else 0,
            "description": res.rule.description if res.rule else "",
        },
    }
    from datetime import datetime

    ch.computed_at = datetime.now()
    if existing and existing.status == ChargeStatus.APPROVED and before and before.get("amount") != ch.amount:
        # שינוי בסכום לאחר אישור מחזיר לטיוטה כדי שייבדק שוב
        ch.status = ChargeStatus.DRAFT
        ch.warnings = list(ch.warnings) + ["הסכום השתנה לאחר האישור – נדרש אישור מחדש"]
    if not existing:
        db.add(ch)
    db.flush()
    audit.log(db, user, "charge", ch.id, "compute", before=before, after=audit.snapshot(ch))
    return ch


def compute_month(db: Session, year: int, month: int, user: User | None) -> list[MonthlyCharge]:
    if is_month_closed(db, year, month):
        return db.query(MonthlyCharge).filter_by(year=year, month=month).all()
    return [save_charge(db, c, year, month, user) for c in active_children_for_month(db, year, month)]


def approve_charge(db: Session, ch: MonthlyCharge, user: User | None) -> None:
    from datetime import datetime

    if ch.status == ChargeStatus.CLOSED:
        return
    before = audit.snapshot(ch)
    ch.status = ChargeStatus.APPROVED
    ch.approved_at = datetime.now()
    ch.approved_by = user.display_name if user else ""
    audit.log(db, user, "charge", ch.id, "approve", before=before, after=audit.snapshot(ch))


def previous_balance(db: Session, child: Child, year: int, month: int) -> float:
    """יתרת חוב מחודשים קודמים (חיובים מאושרים/סגורים פחות תשלומים ששויכו)."""
    total = Decimal("0")
    for ch in db.query(MonthlyCharge).filter(MonthlyCharge.child_id == child.id).all():
        if (ch.year, ch.month) >= (year, month):
            continue
        if ch.status == ChargeStatus.DRAFT:
            continue
        total += Decimal(str(ch.balance))
    return q2(total)
