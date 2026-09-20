from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy.orm import Session

from .. import config
from ..auth import require, require_user
from ..db import get_db
from ..models import Receipt, ReceiptStatus
from ..services import receipts as rcpt_svc
from ..services.ypay import get_provider
from ..web import flash, parse_money, redirect, render

router = APIRouter(prefix="/receipts")


def _provider_info():
    try:
        p = get_provider()
        return {"name": p.name, "supports_email": p.supports_email, "manual": p.requires_manual_number, "error": ""}
    except RuntimeError as e:
        return {"name": config.RECEIPT_PROVIDER, "supports_email": False, "manual": False, "error": str(e)}


@router.get("")
def list_receipts(request: Request, status: str = "", db: Session = Depends(get_db), user=Depends(require_user)):
    q = db.query(Receipt).order_by(Receipt.created_at.desc())
    if status:
        q = q.filter(Receipt.status == ReceiptStatus(status))
    receipts = q.limit(300).all()
    pending = rcpt_svc.pending(db)
    return render(request, "receipts/list.html", user, receipts=receipts, pending=pending, status=status, provider=_provider_info())


def _receipt(db: Session, rid: int) -> Receipt:
    r = db.get(Receipt, rid)
    if not r:
        raise HTTPException(404)
    return r


@router.get("/{rid}")
def detail(request: Request, rid: int, db: Session = Depends(get_db), user=Depends(require_user)):
    r = _receipt(db, rid)
    return render(request, "receipts/detail.html", user, r=r, provider=_provider_info())


@router.post("/{rid}/edit")
def edit(request: Request, rid: int, payer_name: str = Form(""), email: str = Form(""), description: str = Form(""), notes: str = Form(""), amount: str = Form(""), db: Session = Depends(get_db), user=Depends(require("receipts.approve"))):
    r = _receipt(db, rid)
    amt = parse_money(amount)
    if amt is not None and amt > float(r.payment.amount) + 0.004:
        flash(request, "סכום הקבלה לא יכול לעלות על סכום התשלום שהתקבל", "error")
        return redirect(f"/receipts/{rid}")
    try:
        rcpt_svc.update_draft(db, r, user, payer_name=payer_name.strip(), email=email.strip(), description=description.strip(), notes=notes.strip(), amount=amt)
        db.commit()
        flash(request, "הקבלה עודכנה" + (" – נדרש אישור מחדש" if r.status == ReceiptStatus.DRAFT else ""))
    except ValueError as e:
        db.rollback()
        flash(request, str(e), "error")
    return redirect(f"/receipts/{rid}")


@router.post("/{rid}/approve")
def approve(request: Request, rid: int, db: Session = Depends(get_db), user=Depends(require("receipts.approve"))):
    r = _receipt(db, rid)
    try:
        rcpt_svc.approve(db, r, user)
        db.commit()
        flash(request, "הקבלה אושרה להפקה. ההפקה עצמה מתבצעת בלחיצה נפרדת.")
    except ValueError as e:
        db.rollback()
        flash(request, str(e), "error")
    return redirect(f"/receipts/{rid}")


@router.post("/approve-all")
def approve_all(request: Request, ids: list[int] = Form([]), confirm: bool = Form(False), db: Session = Depends(get_db), user=Depends(require("receipts.approve"))):
    """אישור מרוכז – רק לקבלות שסומנו במפורש לאחר שהוצגו לבדיקה."""
    if not confirm:
        flash(request, "יש לסמן שכל הקבלות נבדקו לפני אישור מרוכז", "error")
        return redirect("/receipts")
    n, errors = 0, []
    for rid in ids:
        r = db.get(Receipt, rid)
        if not r:
            continue
        try:
            rcpt_svc.approve(db, r, user)
            n += 1
        except ValueError as e:
            errors.append(f"{r.child.full_name if r.child else rid}: {e}")
    db.commit()
    flash(request, f"אושרו {n} קבלות" + (". שגיאות: " + "; ".join(errors) if errors else ""), "success" if not errors else "warning")
    return redirect("/receipts")


@router.post("/{rid}/issue")
def issue(request: Request, rid: int, confirm: bool = Form(False), manual_number: str = Form(""), db: Session = Depends(get_db), user=Depends(require("receipts.approve"))):
    r = _receipt(db, rid)
    if not confirm:
        flash(request, "יש לאשר במפורש את ההפקה", "error")
        return redirect(f"/receipts/{rid}")
    try:
        rcpt_svc.issue(db, r, user, manual_number=manual_number)
        db.commit()
        if r.status == ReceiptStatus.ISSUED:
            flash(request, f"הקבלה הופקה. מספר קבלה: {r.receipt_number}")
        else:
            flash(request, f"ההפקה נכשלה: {r.error}", "error")
    except (ValueError, RuntimeError) as e:
        db.rollback()
        flash(request, str(e), "error")
    return redirect(f"/receipts/{rid}")


@router.post("/{rid}/send")
def send(request: Request, rid: int, db: Session = Depends(get_db), user=Depends(require("receipts.approve"))):
    r = _receipt(db, rid)
    try:
        rcpt_svc.send(db, r, user)
        db.commit()
        flash(request, f"הקבלה נשלחה ל-{r.email}" if r.status == ReceiptStatus.SENT else f"השליחה נכשלה: {r.error}", "success" if r.status == ReceiptStatus.SENT else "error")
    except (ValueError, RuntimeError) as e:
        db.rollback()
        flash(request, str(e), "error")
    return redirect(f"/receipts/{rid}")


@router.post("/{rid}/mark-sent")
def mark_sent(request: Request, rid: int, db: Session = Depends(get_db), user=Depends(require("receipts.approve"))):
    r = _receipt(db, rid)
    try:
        rcpt_svc.mark_sent_manually(db, r, user)
        db.commit()
        flash(request, "הקבלה סומנה כנשלחה")
    except ValueError as e:
        db.rollback()
        flash(request, str(e), "error")
    return redirect(f"/receipts/{rid}")


@router.post("/{rid}/cancel")
def cancel(request: Request, rid: int, reason: str = Form(""), db: Session = Depends(get_db), user=Depends(require("receipts.approve"))):
    r = _receipt(db, rid)
    try:
        rcpt_svc.cancel(db, r, user, reason)
        db.commit()
        flash(request, "טיוטת הקבלה בוטלה")
    except ValueError as e:
        db.rollback()
        flash(request, str(e), "error")
    return redirect(f"/receipts/{rid}")
