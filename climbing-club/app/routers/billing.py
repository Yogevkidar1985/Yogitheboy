from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy.orm import Session

from .. import audit
from ..auth import require, require_user
from ..db import get_db
from ..models import Adjustment, ChargeStatus, Child, ClubSession, MessageStatus, MonthlyCharge, PaymentMessage
from ..services import billing as billing_svc
from ..services import messages as msg_svc
from ..web import flash, parse_money, prev_next, redirect, render, ym_from_query

router = APIRouter(prefix="/billing")


@router.get("")
def billing_view(request: Request, year: int | None = None, month: int | None = None, db: Session = Depends(get_db), user=Depends(require_user)):
    y, m = ym_from_query(year, month)
    charges = (
        db.query(MonthlyCharge).filter_by(year=y, month=m).join(Child).order_by(Child.full_name).all()
    )
    active = billing_svc.active_children_for_month(db, y, m)
    computed_ids = {c.child_id for c in charges}
    not_computed = [c for c in active if c.id not in computed_ids]
    totals = {
        "amount": sum(float(c.amount) for c in charges),
        "paid": sum(c.paid for c in charges),
        "balance": sum(c.balance for c in charges),
        "warnings": sum(1 for c in charges if c.warnings),
    }
    return render(
        request,
        "billing/month.html",
        user,
        year=y,
        month=m,
        charges=charges,
        not_computed=not_computed,
        totals=totals,
        closed=billing_svc.is_month_closed(db, y, m),
        prev_next=prev_next(y, m),
    )


@router.post("/compute")
def compute(request: Request, year: int = Form(...), month: int = Form(...), db: Session = Depends(get_db), user=Depends(require("billing"))):
    if billing_svc.is_month_closed(db, year, month):
        flash(request, "החודש סגור – החיובים קפואים", "error")
    else:
        charges = billing_svc.compute_month(db, year, month, user)
        db.commit()
        flash(request, f"חושבו {len(charges)} חיובים. יש לבדוק את האזהרות ולאשר.")
    return redirect(f"/billing?year={year}&month={month}")


def _charge(db: Session, cid: int) -> MonthlyCharge:
    ch = db.get(MonthlyCharge, cid)
    if not ch:
        raise HTTPException(404)
    return ch


@router.get("/{cid}")
def charge_detail(request: Request, cid: int, db: Session = Depends(get_db), user=Depends(require_user)):
    ch = _charge(db, cid)
    lines = (ch.detail or {}).get("lines", [])
    sessions = {s.id: s for s in db.query(ClubSession).filter(ClubSession.id.in_([l["session_id"] for l in lines])).all()} if lines else {}
    prev_balance = billing_svc.previous_balance(db, ch.child, ch.year, ch.month)
    return render(request, "billing/charge.html", user, ch=ch, lines=lines, sessions=sessions, prev_balance=prev_balance, closed=ch.status == ChargeStatus.CLOSED)


@router.post("/{cid}/recompute")
def recompute(request: Request, cid: int, custom_amount: str = Form(""), db: Session = Depends(get_db), user=Depends(require("billing"))):
    ch = _charge(db, cid)
    if ch.status == ChargeStatus.CLOSED:
        flash(request, "החיוב סגור", "error")
        return redirect(f"/billing/{cid}")
    billing_svc.save_charge(db, ch.child, ch.year, ch.month, user, custom_amount=parse_money(custom_amount))
    db.commit()
    flash(request, "החיוב חושב מחדש")
    return redirect(f"/billing/{cid}")


@router.post("/{cid}/approve")
def approve(request: Request, cid: int, db: Session = Depends(get_db), user=Depends(require("billing"))):
    ch = _charge(db, cid)
    billing_svc.approve_charge(db, ch, user)
    msg_svc.ensure_message(db, ch, user, regenerate=True)
    db.commit()
    flash(request, f"החיוב של {ch.child.full_name} אושר והוכנה הודעת תשלום")
    return redirect(f"/billing?year={ch.year}&month={ch.month}")


@router.post("/approve-all")
def approve_all(request: Request, year: int = Form(...), month: int = Form(...), db: Session = Depends(get_db), user=Depends(require("billing"))):
    n = 0
    for ch in db.query(MonthlyCharge).filter_by(year=year, month=month, status=ChargeStatus.DRAFT).all():
        if ch.warnings:
            continue  # חיובים עם אזהרות מאושרים רק בנפרד, לאחר בדיקה
        billing_svc.approve_charge(db, ch, user)
        msg_svc.ensure_message(db, ch, user, regenerate=True)
        n += 1
    db.commit()
    flash(request, f"אושרו {n} חיובים ללא אזהרות. חיובים עם אזהרות דורשים אישור פרטני.")
    return redirect(f"/billing?year={year}&month={month}")


@router.post("/adjustments")
def add_adjustment(request: Request, child_id: int = Form(...), year: int = Form(...), month: int = Form(...), amount: str = Form(...), reason: str = Form(...), session_id: int | None = Form(None), back: str = Form(""), db: Session = Depends(get_db), user=Depends(require("billing"))):
    if billing_svc.is_month_closed(db, year, month):
        flash(request, "החודש סגור", "error")
        return redirect(back or f"/billing?year={year}&month={month}")
    amt = parse_money(amount)
    if amt is None or amt == 0:
        flash(request, "סכום לא תקין", "error")
        return redirect(back or f"/billing?year={year}&month={month}")
    a = Adjustment(child_id=child_id, year=year, month=month, amount=amt, reason=reason.strip(), session_id=session_id, created_by=user.display_name)
    db.add(a)
    db.flush()
    audit.log(db, user, "adjustment", a.id, "create", after=audit.snapshot(a))
    child = db.get(Child, child_id)
    ch = billing_svc.save_charge(db, child, year, month, user)
    db.commit()
    flash(request, "ההתאמה נשמרה והחיוב חושב מחדש")
    return redirect(back or f"/billing/{ch.id}")


@router.post("/adjustments/{aid}/delete")
def delete_adjustment(request: Request, aid: int, back: str = Form(""), db: Session = Depends(get_db), user=Depends(require("billing"))):
    a = db.get(Adjustment, aid)
    if not a:
        raise HTTPException(404)
    if billing_svc.is_month_closed(db, a.year, a.month):
        flash(request, "החודש סגור", "error")
        return redirect(back or "/billing")
    before = audit.snapshot(a)
    child, y, m = a.child, a.year, a.month
    db.delete(a)
    audit.log(db, user, "adjustment", aid, "delete", before=before)
    ch = billing_svc.save_charge(db, child, y, m, user)
    db.commit()
    flash(request, "ההתאמה נמחקה")
    return redirect(back or f"/billing/{ch.id}")


# ---- הודעות תשלום


@router.get("/messages/list")
def messages_view(request: Request, year: int | None = None, month: int | None = None, db: Session = Depends(get_db), user=Depends(require_user)):
    y, m = ym_from_query(year, month)
    charges = db.query(MonthlyCharge).filter(MonthlyCharge.year == y, MonthlyCharge.month == m, MonthlyCharge.status != ChargeStatus.DRAFT).join(Child).order_by(Child.full_name).all()
    for ch in charges:
        if ch.message is None:
            msg_svc.ensure_message(db, ch, user)
    db.commit()
    items = [(ch, ch.message, msg_svc.whatsapp_link(ch.message.recipient_phone, ch.message.body)) for ch in charges]
    return render(request, "billing/messages.html", user, year=y, month=m, items=items, prev_next=prev_next(y, m))


@router.post("/messages/{mid}/approve")
def approve_message(request: Request, mid: int, body: str = Form(...), db: Session = Depends(get_db), user=Depends(require("billing"))):
    msg = db.get(PaymentMessage, mid)
    if not msg:
        raise HTTPException(404)
    if msg.status == MessageStatus.SENT:
        flash(request, "ההודעה כבר נשלחה", "error")
    else:
        msg_svc.approve(db, msg, user, body=body)
        db.commit()
        flash(request, "ההודעה אושרה")
    return redirect(f"/billing/messages/list?year={msg.charge.year}&month={msg.charge.month}")


@router.post("/messages/{mid}/regenerate")
def regenerate_message(request: Request, mid: int, db: Session = Depends(get_db), user=Depends(require("billing"))):
    msg = db.get(PaymentMessage, mid)
    if not msg:
        raise HTTPException(404)
    msg_svc.ensure_message(db, msg.charge, user, regenerate=True)
    db.commit()
    flash(request, "ההודעה נוצרה מחדש מהתבנית")
    return redirect(f"/billing/messages/list?year={msg.charge.year}&month={msg.charge.month}")


@router.post("/messages/{mid}/sent")
def sent_message(request: Request, mid: int, db: Session = Depends(get_db), user=Depends(require("attendance"))):
    msg = db.get(PaymentMessage, mid)
    if not msg:
        raise HTTPException(404)
    try:
        msg_svc.mark_sent(db, msg, user)
        db.commit()
        flash(request, "ההודעה סומנה כנשלחה")
    except ValueError as e:
        db.rollback()
        flash(request, str(e), "error")
    return redirect(f"/billing/messages/list?year={msg.charge.year}&month={msg.charge.month}")
