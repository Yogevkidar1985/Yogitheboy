from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy.orm import Session

from .. import audit
from ..auth import require, require_user
from ..db import get_db
from ..models import (
    Attendance,
    AttendanceStatus,
    Child,
    ChildContact,
    ChildStatus,
    ClubSession,
    Contact,
    IntroSession,
    PaymentMethod,
    SessionKind,
    SessionStatus,
)
from ..services import payments as pay_svc
from ..services import receipts as rcpt_svc
from ..services import settings as settings_svc
from ..web import flash, parse_date, parse_money, redirect, render

router = APIRouter(prefix="/intro")


@router.get("")
def list_intro(request: Request, db: Session = Depends(get_db), user=Depends(require_user)):
    items = db.query(IntroSession).order_by(IntroSession.created_at.desc()).all()
    return render(request, "intro/list.html", user, items=items)


@router.get("/new")
def new_intro(request: Request, db: Session = Depends(get_db), user=Depends(require("payments.add"))):
    children = db.query(Child).order_by(Child.full_name).all()
    return render(request, "intro/form.html", user, children=children, default_price=settings_svc.get(db, "intro_session_price"))


@router.post("")
def create_intro(
    request: Request,
    child_id: str = Form(""),
    child_name: str = Form(""),
    child_national_id: str = Form(""),
    parent_name: str = Form(""),
    parent_phone: str = Form(""),
    parent_email: str = Form(""),
    session_date: str = Form(...),
    amount: str = Form(...),
    notes: str = Form(""),
    # תשלום (אופציונלי בשלב זה)
    paid: bool = Form(False),
    paid_on: str = Form(""),
    method: str = Form("bank_transfer"),
    reference: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(require("payments.add")),
):
    d = parse_date(session_date)
    amt = parse_money(amount)
    if not d or amt is None or amt <= 0:
        flash(request, "תאריך או סכום לא תקינים", "error")
        return redirect("/intro/new")
    if child_id:
        child = db.get(Child, int(child_id))
        if not child:
            raise HTTPException(404)
    else:
        if not child_name.strip():
            flash(request, "יש להזין שם ילד או לבחור מהמאגר", "error")
            return redirect("/intro/new")
        child = Child(full_name=child_name.strip(), national_id=child_national_id.strip(), status=ChildStatus.PAUSED, joined_on=d, notes="נוצר ממפגש היכרות")
        db.add(child)
        db.flush()
        if parent_name.strip():
            ct = Contact(full_name=parent_name.strip(), phone=parent_phone.strip(), email=parent_email.strip())
            db.add(ct)
            db.flush()
            db.add(ChildContact(child_id=child.id, contact_id=ct.id, relation="הורה"))
        audit.log(db, user, "child", child.id, "create_intro", after=audit.snapshot(child))
    s = ClubSession(date=d, group_id=None, kind=SessionKind.INTRO, status=SessionStatus.HELD if d <= date.today() else SessionStatus.PLANNED, reason="מפגש היכרות", created_by=user.display_name)
    db.add(s)
    db.flush()
    db.add(Attendance(session_id=s.id, child_id=child.id, status=AttendanceStatus.PRESENT if d <= date.today() else AttendanceStatus.UNREPORTED, reported_by=user.display_name))
    intro = IntroSession(child_id=child.id, session_id=s.id, amount=amt, notes=notes.strip())
    db.add(intro)
    db.flush()
    if paid:
        p = pay_svc.create_payment(
            db, user, child_id=child.id, paid_on=parse_date(paid_on) or date.today(), amount=amt, method=PaymentMethod(method), payer_name=parent_name.strip() or (child.billing_contact.full_name if child.billing_contact else ""), reference=reference.strip(), notes="מפגש היכרות"
        )
        intro.payment_id = p.id
        db.flush()
        rcpt_svc.prepare_for_payment(db, p, user)
    audit.log(db, user, "intro_session", intro.id, "create", after=audit.snapshot(intro))
    db.commit()
    flash(request, "מפגש ההיכרות נרשם" + (" והוכנה טיוטת קבלה לבדיקה" if paid else ""))
    return redirect(f"/intro/{intro.id}")


@router.get("/{iid}")
def intro_detail(request: Request, iid: int, db: Session = Depends(get_db), user=Depends(require_user)):
    intro = db.get(IntroSession, iid)
    if not intro:
        raise HTTPException(404)
    receipts = intro.payment.receipts if intro.payment else []
    return render(request, "intro/detail.html", user, intro=intro, receipts=receipts)


@router.post("/{iid}/pay")
def intro_pay(request: Request, iid: int, paid_on: str = Form(""), method: str = Form("bank_transfer"), reference: str = Form(""), payer_name: str = Form(""), db: Session = Depends(get_db), user=Depends(require("payments.add"))):
    intro = db.get(IntroSession, iid)
    if not intro:
        raise HTTPException(404)
    if intro.payment_id:
        flash(request, "כבר נקלט תשלום למפגש זה", "error")
        return redirect(f"/intro/{iid}")
    p = pay_svc.create_payment(db, user, child_id=intro.child_id, paid_on=parse_date(paid_on) or date.today(), amount=float(intro.amount), method=PaymentMethod(method), payer_name=payer_name.strip(), reference=reference.strip(), notes="מפגש היכרות")
    intro.payment_id = p.id
    db.flush()
    rcpt_svc.prepare_for_payment(db, p, user)
    db.commit()
    flash(request, "התשלום נקלט והוכנה טיוטת קבלה לבדיקה")
    return redirect(f"/intro/{iid}")
