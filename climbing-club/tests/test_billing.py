from datetime import date

from app.models import AttendanceStatus, BillingMethod, BillingRule, ChargeOverride, ChargeStatus, SessionStatus
from app.services import attendance as att
from app.services import billing
from app.services import calendar as cal
from app.services import settings as settings_svc
from tests.conftest import make_child


def _setup_sept(db, user, groups, child):
    """7 מפגשים התקיימו לילד בקבוצת ראשון+רביעי, נכח ב-6, החסיר 1, מפגש אחד בוטל (חג)."""
    sessions = cal.generate_month(db, 2026, 9, user)
    holiday = next(s for s in sessions if s.date == date(2026, 9, 13))
    cal.cancel_session(db, holiday, SessionStatus.CANCELLED_HOLIDAY, "ראש השנה", user)
    held = [s for s in sessions if s is not holiday][:7]
    for i, s in enumerate(held):
        att.bulk_set(db, s, {child.id: AttendanceStatus.ABSENT if i == 3 else AttendanceStatus.PRESENT}, user)
    return held


def test_per_attendance_example_from_spec(db, user, groups):
    child = make_child(db, "נועה", groups, BillingMethod.PER_ATTENDANCE, price=150)
    _setup_sept(db, user, groups, child)
    res = billing.compute(db, child, 2026, 9)
    assert (res.sessions_held, res.sessions_attended, res.sessions_absent, res.sessions_cancelled) == (7, 6, 1, 1)
    assert res.amount == 900.0 and not res.warnings


def test_per_held_session_charges_absences(db, user, groups):
    child = make_child(db, "איתי", groups, BillingMethod.PER_HELD_SESSION, price=150)
    _setup_sept(db, user, groups, child)
    res = billing.compute(db, child, 2026, 9)
    assert res.amount == 7 * 150


def test_fixed_monthly_ignores_attendance_and_warns_when_policy_unset(db, user, groups):
    child = make_child(db, "תמר", groups, BillingMethod.FIXED_MONTHLY, price=150, fixed=1000)
    _setup_sept(db, user, groups, child)
    res = billing.compute(db, child, 2026, 9)
    assert res.amount == 1000 and any("טרם הוגדרה" in w for w in res.warnings)
    settings_svc.set_(db, "cancel_policy_fixed_monthly", settings_svc.CANCEL_POLICY_CREDIT)
    assert billing.compute(db, child, 2026, 9).amount == 850
    settings_svc.set_(db, "cancel_policy_fixed_monthly", settings_svc.CANCEL_POLICY_NO_CHANGE)
    assert billing.compute(db, child, 2026, 9).amount == 1000


def test_custom_requires_manual_amount(db, user, groups):
    child = make_child(db, "עידו", groups, BillingMethod.CUSTOM)
    _setup_sept(db, user, groups, child)
    res = billing.compute(db, child, 2026, 9)
    assert res.amount == 0 and any("ידנית" in w for w in res.warnings)
    ch = billing.save_charge(db, child, 2026, 9, user, custom_amount=700)
    assert float(ch.amount) == 700
    # חישוב מחדש שומר את הסכום הידני
    assert float(billing.save_charge(db, child, 2026, 9, user).amount) == 700


def test_unreported_is_not_absent(db, user, groups):
    child = make_child(db, "מאיה", groups, BillingMethod.PER_ATTENDANCE, price=100)
    sessions = cal.generate_month(db, 2026, 9, user)
    att.bulk_set(db, sessions[0], {child.id: AttendanceStatus.PRESENT}, user)
    cal.mark_held(db, sessions[1], user)  # התקיים, אך לא דווח
    res = billing.compute(db, child, 2026, 9)
    assert res.sessions_held == 2 and res.sessions_attended == 1 and res.sessions_absent == 0 and res.sessions_unreported == 1
    assert res.amount == 100 and any("ללא דיווח" in w for w in res.warnings)


def test_session_override_and_adjustment(db, user, groups):
    from app.models import Adjustment

    child = make_child(db, "לביא", groups, BillingMethod.PER_ATTENDANCE, price=160)
    held = _setup_sept(db, user, groups, child)
    rec = att.records_for(db, held[3])[child.id]  # ההיעדרות
    rec.charge_override = ChargeOverride.CHARGE
    rec.price_override = 80
    db.flush()
    db.add(Adjustment(child_id=child.id, year=2026, month=9, amount=-100, reason="זיכוי"))
    db.flush()
    res = billing.compute(db, child, 2026, 9)
    assert res.base_amount == 6 * 160 + 80 and res.adjustments_total == -100 and res.amount == 6 * 160 + 80 - 100


def test_rate_history_uses_rule_effective_on_session_date(db, user, groups):
    child = make_child(db, "היסטוריה", groups, BillingMethod.PER_ATTENDANCE, price=100)
    child.billing_rules[0].effective_to = date(2026, 9, 15)
    db.add(BillingRule(child_id=child.id, effective_from=date(2026, 9, 16), method=BillingMethod.PER_ATTENDANCE, price_per_session=200))
    db.flush()
    db.refresh(child)
    sessions = cal.generate_month(db, 2026, 9, user)
    early = next(s for s in sessions if s.date == date(2026, 9, 6))
    late = next(s for s in sessions if s.date == date(2026, 9, 20))
    att.bulk_set(db, early, {child.id: AttendanceStatus.PRESENT}, user)
    att.bulk_set(db, late, {child.id: AttendanceStatus.PRESENT}, user)
    assert billing.compute(db, child, 2026, 9).amount == 300


def test_closed_charge_is_frozen(db, user, groups):
    from app.services import month_close

    child = make_child(db, "קפוא", groups, BillingMethod.PER_ATTENDANCE, price=150)
    _setup_sept(db, user, groups, child)
    ch = billing.save_charge(db, child, 2026, 9, user)
    billing.approve_charge(db, ch, user)
    # סוגרים את שאר המפגשים המתוכננים כדי לעבור את הבדיקות
    for s in cal.month_sessions(db, 2026, 9):
        if s.status == SessionStatus.PLANNED:
            cal.cancel_session(db, s, SessionStatus.CANCELLED_ADMIN, "סוף", user)
    month_close.close_month(db, 2026, 9, user)
    assert ch.status == ChargeStatus.CLOSED
    child.billing_rules[0].price_per_session = 999
    db.flush()
    assert float(billing.save_charge(db, child, 2026, 9, user).amount) == 900


def test_approved_charge_returns_to_draft_when_amount_changes(db, user, groups):
    child = make_child(db, "שינוי", groups, BillingMethod.PER_ATTENDANCE, price=150)
    held = _setup_sept(db, user, groups, child)
    ch = billing.save_charge(db, child, 2026, 9, user)
    billing.approve_charge(db, ch, user)
    att.bulk_set(db, held[3], {child.id: AttendanceStatus.PRESENT}, user)
    ch = billing.save_charge(db, child, 2026, 9, user)
    assert ch.status == ChargeStatus.DRAFT and float(ch.amount) == 1050
