from datetime import date

import pytest

from app.models import AttendanceStatus, BillingMethod, PaymentMethod, ReceiptMode, ReceiptStatus, SessionStatus
from app.services import attendance as att
from app.services import billing
from app.services import calendar as cal
from app.services import messages as msg
from app.services import payments as pay
from app.services import receipts as rc
from tests.conftest import make_child


def _charged_child(db, user, groups, **kw):
    child = make_child(db, kw.pop("name", "נועה"), groups, kw.pop("method", BillingMethod.PER_ATTENDANCE), **kw)
    sessions = cal.generate_month(db, 2026, 9, user) or cal.month_sessions(db, 2026, 9)
    for s in sessions[:3]:
        att.bulk_set(db, s, {child.id: AttendanceStatus.PRESENT}, user)
    ch = billing.save_charge(db, child, 2026, 9, user)
    billing.approve_charge(db, ch, user)
    return child, ch


def test_partial_payment_and_multi_month_allocation(db, user, groups):
    child, ch_sep = _charged_child(db, user, groups, price=100)  # 300
    # חודש נוסף
    sessions = cal.generate_month(db, 2026, 10, user)
    att.bulk_set(db, sessions[0], {child.id: AttendanceStatus.PRESENT}, user)
    ch_oct = billing.save_charge(db, child, 2026, 10, user)
    billing.approve_charge(db, ch_oct, user)  # 100
    p = pay.create_payment(db, user, child_id=child.id, paid_on=date(2026, 10, 5), amount=350, method=PaymentMethod.BIT)
    allocs = pay.auto_allocate(db, p, user)
    assert [(a.charge_id, float(a.amount)) for a in allocs] == [(ch_sep.id, 300.0), (ch_oct.id, 50.0)]
    assert ch_sep.balance == 0 and ch_oct.balance == 50 and p.unallocated == 0
    with pytest.raises(ValueError):
        pay.allocate(db, p, ch_oct, 10, user)


def test_duplicate_detection(db, user, groups):
    child, _ = _charged_child(db, user, groups)
    pay.create_payment(db, user, child_id=child.id, paid_on=date(2026, 9, 1), amount=200, reference="R1")
    assert pay.find_duplicates(db, 200, date(2026, 9, 1))
    assert pay.find_duplicates(db, 999, date(2026, 1, 1), reference="R1")
    assert not pay.find_duplicates(db, 200, date(2026, 9, 2), reference="R2")


def test_monthly_receipt_flow_is_idempotent(db, user, groups):
    child, ch = _charged_child(db, user, groups, price=100)
    p = pay.create_payment(db, user, child_id=child.id, paid_on=date(2026, 10, 1), amount=300, method=PaymentMethod.BANK_TRANSFER, reference="77")
    pay.auto_allocate(db, p, user)
    receipts = rc.prepare_for_payment(db, p, user)
    assert len(receipts) == 1 and receipts[0].amount == 300 and receipts[0].email == "p@example.com"
    assert len(receipts[0].data["session_dates"]) == 3
    assert rc.prepare_for_payment(db, p, user) == []  # אין כפילות
    r = receipts[0]
    with pytest.raises(ValueError):
        rc.issue(db, r, user)  # לא אושרה
    rc.approve(db, r, user)
    rc.issue(db, r, user)
    assert r.status == ReceiptStatus.ISSUED and r.receipt_number.startswith("SIM-")
    with pytest.raises(ValueError):
        rc.issue(db, r, user)  # הפקה כפולה חסומה
    rc.send(db, r, user)
    assert r.status == ReceiptStatus.SENT


def test_per_session_receipts_split_by_session(db, user, groups):
    child, ch = _charged_child(db, user, groups, name="לביא", price=160, receipt_mode=ReceiptMode.PER_SESSION, hmo="מכבי")
    p = pay.create_payment(db, user, child_id=child.id, paid_on=date(2026, 10, 1), amount=480)
    pay.auto_allocate(db, p, user)
    receipts = rc.prepare_for_payment(db, p, user)
    assert len(receipts) == 3 and all(float(r.amount) == 160 for r in receipts)
    assert len({r.session_id for r in receipts}) == 3 and all("מכבי" in r.notes for r in receipts)


def test_missing_email_blocks_approval(db, user, groups):
    child, ch = _charged_child(db, user, groups, email="")
    p = pay.create_payment(db, user, child_id=child.id, paid_on=date(2026, 10, 1), amount=450)
    pay.auto_allocate(db, p, user)
    r = rc.prepare_for_payment(db, p, user)[0]
    assert "כתובת מייל לשליחה" in r.missing_fields
    with pytest.raises(ValueError):
        rc.approve(db, r, user)
    rc.update_draft(db, r, user, email="new@example.com")
    rc.approve(db, r, user)
    assert r.status == ReceiptStatus.APPROVED


def test_receipt_requires_allocation(db, user, groups):
    child, _ = _charged_child(db, user, groups)
    p = pay.create_payment(db, user, child_id=child.id, paid_on=date(2026, 10, 1), amount=10)
    with pytest.raises(ValueError):
        rc.prepare_for_payment(db, p, user)


def test_payment_message_and_double_send_guard(db, user, groups):
    child, ch = _charged_child(db, user, groups, price=150)
    m = msg.ensure_message(db, ch, user)
    assert "450" in m.body and child.full_name in m.body and "ספיר ויהלי" in m.body
    msg.approve(db, m, user)
    msg.mark_sent(db, m, user)
    with pytest.raises(ValueError):
        msg.mark_sent(db, m, user)
    assert msg.whatsapp_link("052-1234567", "hi").startswith("https://wa.me/972521234567?text=")


def test_family_payment_covers_siblings(db, user, groups):
    from app.models import ChildContact, Contact

    a, ch_a = _charged_child(db, user, groups, name="אח", price=100)   # 300
    b, ch_b = _charged_child(db, user, groups, name="אחות", price=100)  # 300
    shared = Contact(full_name="הורה משותף", email="fam@example.com")
    db.add(shared)
    db.flush()
    db.add_all([ChildContact(child_id=a.id, contact_id=shared.id), ChildContact(child_id=b.id, contact_id=shared.id)])
    db.flush()
    db.refresh(a)
    assert [c.id for c in a.siblings()] == [b.id]
    fam = pay.family_open_charges(db, a)
    assert [(c.id, ch.id) for c, ch in fam] == [(a.id, ch_a.id), (b.id, ch_b.id)]
    p = pay.create_payment(db, user, child_id=a.id, paid_on=date(2026, 10, 1), amount=600)
    pay.allocate(db, p, ch_a, 300, user)
    pay.allocate(db, p, ch_b, 300, user)
    receipts = rc.prepare_for_payment(db, p, user)
    assert {r.child_id for r in receipts} == {a.id, b.id} and all(float(r.amount) == 300 for r in receipts)
