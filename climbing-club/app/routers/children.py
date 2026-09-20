from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy.orm import Session

from .. import audit
from ..auth import require, require_user
from ..db import get_db
from ..models import (
    BillingMethod,
    BillingRule,
    Child,
    ChildContact,
    ChildStatus,
    Contact,
    Group,
    Membership,
    MonthlyCharge,
    Payment,
    Receipt,
    ReceiptMode,
)
from ..services import settings as settings_svc
from ..services.attendance import child_history
from ..web import flash, parse_date, parse_money, redirect, render

router = APIRouter(prefix="/children")


def _get_child(db: Session, child_id: int) -> Child:
    c = db.get(Child, child_id)
    if not c:
        raise HTTPException(404)
    return c


@router.get("")
def list_children(request: Request, q: str = "", status: str = "", group_id: int | None = None, db: Session = Depends(get_db), user=Depends(require_user)):
    query = db.query(Child)
    if q:
        query = query.filter(Child.full_name.contains(q))
    if status:
        query = query.filter(Child.status == ChildStatus(status))
    children = query.order_by(Child.status, Child.full_name).all()
    if group_id:
        children = [c for c in children if any(m.group_id == group_id for m in c.memberships)]
    groups = db.query(Group).order_by(Group.weekday).all()
    balances: dict[int, float] = {}
    for ch in db.query(MonthlyCharge).filter(MonthlyCharge.status != "draft").all():
        balances[ch.child_id] = round(balances.get(ch.child_id, 0) + ch.balance, 2)
    return render(request, "children/list.html", user, children=children, groups=groups, q=q, status=status, group_id=group_id, balances=balances)


@router.get("/new")
def new_child(request: Request, copy_from: int | None = None, db: Session = Depends(get_db), user=Depends(require("children.edit"))):
    groups = db.query(Group).filter(Group.is_active.is_(True)).order_by(Group.weekday).all()
    source = db.get(Child, copy_from) if copy_from else None
    return render(request, "children/form.html", user, child=None, source=source, groups=groups, default_price=settings_svc.get(db, "default_price_per_session"))


@router.post("")
def create_child(
    request: Request,
    full_name: str = Form(...),
    national_id: str = Form(""),
    status: str = Form("active"),
    joined_on: str = Form(""),
    receipt_mode: str = Form("monthly"),
    hmo: str = Form(""),
    receipt_notes: str = Form(""),
    receipt_required_fields: str = Form(""),
    notes: str = Form(""),
    group_ids: list[int] = Form([]),
    # הורה / משלם ראשון
    contact_name: str = Form(""),
    contact_phone: str = Form(""),
    contact_email: str = Form(""),
    contact_relation: str = Form("הורה"),
    # כלל חיוב ראשון
    method: str = Form("per_attendance"),
    price_per_session: str = Form(""),
    fixed_monthly_amount: str = Form(""),
    rule_description: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(require("children.edit")),
):
    if db.query(Child).filter(Child.full_name == full_name.strip(), Child.national_id == national_id.strip()).first():
        flash(request, "כבר קיים ילד עם אותו שם ותעודת זהות – לא נוצרה רשומה כפולה", "error")
        return redirect("/children")
    c = Child(
        full_name=full_name.strip(),
        national_id=national_id.strip(),
        status=ChildStatus(status),
        joined_on=parse_date(joined_on) or date.today(),
        receipt_mode=ReceiptMode(receipt_mode),
        hmo=hmo.strip(),
        receipt_notes=receipt_notes.strip(),
        receipt_required_fields=receipt_required_fields.strip(),
        notes=notes.strip(),
    )
    db.add(c)
    db.flush()
    for gid in group_ids:
        db.add(Membership(child_id=c.id, group_id=gid, from_date=c.joined_on))
    if contact_name.strip():
        ct = Contact(full_name=contact_name.strip(), phone=contact_phone.strip(), email=contact_email.strip())
        db.add(ct)
        db.flush()
        db.add(ChildContact(child_id=c.id, contact_id=ct.id, relation=contact_relation))
    db.add(
        BillingRule(
            child_id=c.id,
            effective_from=c.joined_on.replace(day=1),
            method=BillingMethod(method),
            price_per_session=parse_money(price_per_session) or 0,
            fixed_monthly_amount=parse_money(fixed_monthly_amount) or 0,
            description=rule_description.strip(),
        )
    )
    audit.log(db, user, "child", c.id, "create", after=audit.snapshot(c))
    db.commit()
    flash(request, f"{c.full_name} נוסף/ה למערכת")
    return redirect(f"/children/{c.id}")


@router.get("/{child_id}")
def child_card(request: Request, child_id: int, db: Session = Depends(get_db), user=Depends(require_user)):
    c = _get_child(db, child_id)
    groups = db.query(Group).order_by(Group.weekday).all()
    charges = db.query(MonthlyCharge).filter_by(child_id=c.id).order_by(MonthlyCharge.year.desc(), MonthlyCharge.month.desc()).all()
    payments = db.query(Payment).filter_by(child_id=c.id).order_by(Payment.paid_on.desc()).all()
    receipts = db.query(Receipt).filter_by(child_id=c.id).order_by(Receipt.created_at.desc()).all()
    history = child_history(db, c)[:40]
    return render(
        request,
        "children/card.html",
        user,
        child=c,
        groups=groups,
        charges=charges,
        payments=payments,
        receipts=receipts,
        history=history,
        rule=c.current_rule(),
        methods=BillingMethod,
        open_balance=round(sum(ch.balance for ch in charges if ch.status.value != "draft"), 2),
    )


@router.post("/{child_id}")
def update_child(
    request: Request,
    child_id: int,
    full_name: str = Form(...),
    national_id: str = Form(""),
    status: str = Form("active"),
    joined_on: str = Form(""),
    left_on: str = Form(""),
    birth_date: str = Form(""),
    receipt_mode: str = Form("monthly"),
    hmo: str = Form(""),
    receipt_notes: str = Form(""),
    receipt_required_fields: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(require("children.edit")),
):
    c = _get_child(db, child_id)
    before = audit.snapshot(c)
    c.full_name = full_name.strip()
    c.national_id = national_id.strip()
    c.status = ChildStatus(status)
    c.joined_on = parse_date(joined_on)
    c.left_on = parse_date(left_on)
    c.birth_date = parse_date(birth_date)
    c.receipt_mode = ReceiptMode(receipt_mode)
    c.hmo = hmo.strip()
    c.receipt_notes = receipt_notes.strip()
    c.receipt_required_fields = receipt_required_fields.strip()
    c.notes = notes.strip()
    if c.status == ChildStatus.LEFT and not c.left_on:
        c.left_on = date.today()
    audit.log(db, user, "child", c.id, "update", before=before, after=audit.snapshot(c))
    db.commit()
    flash(request, "פרטי הילד נשמרו")
    return redirect(f"/children/{c.id}")


@router.post("/{child_id}/contacts")
def add_contact(
    request: Request,
    child_id: int,
    contact_id: int | None = Form(None),
    full_name: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    national_id: str = Form(""),
    relation: str = Form("הורה"),
    is_message_contact: bool = Form(False),
    is_billing_contact: bool = Form(False),
    db: Session = Depends(get_db),
    user=Depends(require("children.edit")),
):
    c = _get_child(db, child_id)
    if contact_id:
        ct = db.get(Contact, contact_id)
    else:
        if not full_name.strip():
            flash(request, "יש להזין שם איש קשר", "error")
            return redirect(f"/children/{c.id}")
        ct = Contact(full_name=full_name.strip(), phone=phone.strip(), email=email.strip(), national_id=national_id.strip())
        db.add(ct)
        db.flush()
    if any(cc.contact_id == ct.id for cc in c.contacts):
        flash(request, "איש הקשר כבר משויך לילד", "error")
        return redirect(f"/children/{c.id}")
    cc = ChildContact(child_id=c.id, contact_id=ct.id, relation=relation, is_message_contact=is_message_contact, is_billing_contact=is_billing_contact)
    db.add(cc)
    audit.log(db, user, "child_contact", None, "create", after={"child_id": c.id, "contact_id": ct.id})
    db.commit()
    flash(request, "איש הקשר נוסף")
    return redirect(f"/children/{c.id}")


@router.post("/{child_id}/contacts/{cc_id}")
def update_contact(
    request: Request,
    child_id: int,
    cc_id: int,
    full_name: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    national_id: str = Form(""),
    relation: str = Form("הורה"),
    is_message_contact: bool = Form(False),
    is_billing_contact: bool = Form(False),
    delete: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(require("children.edit")),
):
    cc = db.get(ChildContact, cc_id)
    if not cc or cc.child_id != child_id:
        raise HTTPException(404)
    if delete:
        db.delete(cc)
        db.commit()
        flash(request, "השיוך הוסר")
        return redirect(f"/children/{child_id}")
    before = audit.snapshot(cc.contact)
    cc.contact.full_name = full_name.strip() or cc.contact.full_name
    cc.contact.phone = phone.strip()
    cc.contact.email = email.strip()
    cc.contact.national_id = national_id.strip()
    cc.relation = relation
    cc.is_message_contact = is_message_contact
    cc.is_billing_contact = is_billing_contact
    audit.log(db, user, "contact", cc.contact.id, "update", before=before, after=audit.snapshot(cc.contact))
    db.commit()
    flash(request, "פרטי איש הקשר עודכנו")
    return redirect(f"/children/{child_id}")


@router.post("/{child_id}/rules")
def add_rule(
    request: Request,
    child_id: int,
    effective_from: str = Form(...),
    method: str = Form(...),
    price_per_session: str = Form(""),
    fixed_monthly_amount: str = Form(""),
    description: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(require("children.edit")),
):
    c = _get_child(db, child_id)
    eff = parse_date(effective_from)
    if not eff:
        flash(request, "תאריך תחילת תוקף אינו תקין", "error")
        return redirect(f"/children/{c.id}")
    # סוגרים את הכלל הקודם יום לפני – היסטוריית תעריפים נשמרת
    for r in c.billing_rules:
        if r.effective_to is None and r.effective_from < eff:
            r.effective_to = date.fromordinal(eff.toordinal() - 1)
        elif r.effective_from == eff:
            flash(request, "כבר קיים כלל חיוב שמתחיל בתאריך זה", "error")
            return redirect(f"/children/{c.id}")
    rule = BillingRule(
        child_id=c.id,
        effective_from=eff,
        method=BillingMethod(method),
        price_per_session=parse_money(price_per_session) or 0,
        fixed_monthly_amount=parse_money(fixed_monthly_amount) or 0,
        description=description.strip(),
    )
    db.add(rule)
    db.flush()
    audit.log(db, user, "billing_rule", rule.id, "create", after=audit.snapshot(rule))
    db.commit()
    flash(request, "כלל החיוב נשמר. חודשים שכבר נסגרו אינם משתנים.")
    return redirect(f"/children/{c.id}")


@router.post("/{child_id}/memberships")
def add_membership(
    request: Request,
    child_id: int,
    group_id: int = Form(...),
    from_date: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(require("children.edit")),
):
    c = _get_child(db, child_id)
    if any(m.group_id == group_id and m.to_date is None for m in c.memberships):
        flash(request, "הילד כבר משויך לקבוצה זו", "error")
        return redirect(f"/children/{c.id}")
    m = Membership(child_id=c.id, group_id=group_id, from_date=parse_date(from_date) or date.today())
    db.add(m)
    db.commit()
    flash(request, "השיוך לקבוצה נשמר")
    return redirect(f"/children/{c.id}")


@router.post("/{child_id}/memberships/{mid}/end")
def end_membership(request: Request, child_id: int, mid: int, to_date: str = Form(""), db: Session = Depends(get_db), user=Depends(require("children.edit"))):
    m = db.get(Membership, mid)
    if not m or m.child_id != child_id:
        raise HTTPException(404)
    m.to_date = parse_date(to_date) or date.today()
    db.commit()
    flash(request, "השיוך לקבוצה הסתיים")
    return redirect(f"/children/{child_id}")


@router.get("/contacts/search")
def search_contacts(q: str = "", db: Session = Depends(get_db), user=Depends(require_user)):
    rows = db.query(Contact).filter(Contact.full_name.contains(q)).limit(10).all() if q else []
    return [{"id": r.id, "name": r.full_name, "phone": r.phone, "email": r.email} for r in rows]
