from __future__ import annotations

import secrets
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import audit, config
from ..auth import can, require, require_user
from ..db import get_db
from ..models import Child, ChildStatus, MonthlyCharge, Payment, PaymentAllocation, PaymentMethod, PaymentSource
from ..services import ocr as ocr_svc
from ..services import payments as pay_svc
from ..services import receipts as rcpt_svc
from ..web import flash, parse_date, parse_money, redirect, render

router = APIRouter(prefix="/payments")


def _children(db: Session) -> list[Child]:
    return db.query(Child).filter(Child.status != ChildStatus.LEFT).order_by(Child.full_name).all()


@router.get("")
def list_payments(request: Request, filter: str = "", child_id: int | None = None, db: Session = Depends(get_db), user=Depends(require_user)):
    q = db.query(Payment).order_by(Payment.paid_on.desc(), Payment.id.desc())
    if child_id:
        q = q.filter(Payment.child_id == child_id)
    payments = q.limit(300).all()
    if filter == "unassigned":
        payments = [p for p in payments if p.child_id is None or p.unallocated > 0.004]
    return render(request, "payments/list.html", user, payments=payments, filter=filter, children=_children(db), child_id=child_id, show_bank=can(user, "payments.bank_details"))


@router.get("/new")
def new_payment(request: Request, child_id: int | None = None, db: Session = Depends(get_db), user=Depends(require("payments.add"))):
    child = db.get(Child, child_id) if child_id else None
    open_charges = pay_svc.open_charges_for_child(db, child) if child else []
    return render(request, "payments/form.html", user, children=_children(db), child=child, open_charges=open_charges, prefill={}, extraction=None, attachment="")


@router.post("")
def create_payment(
    request: Request,
    child_id: str = Form(""),
    paid_on: str = Form(...),
    amount: str = Form(...),
    method: str = Form("bank_transfer"),
    payer_name: str = Form(""),
    reference: str = Form(""),
    bank_details: str = Form(""),
    notes: str = Form(""),
    attachment: str = Form(""),
    source: str = Form("manual"),
    force: bool = Form(False),
    auto_alloc: bool = Form(True),
    db: Session = Depends(get_db),
    user=Depends(require("payments.add")),
):
    d = parse_date(paid_on)
    amt = parse_money(amount)
    if not d or amt is None or amt <= 0:
        flash(request, "תאריך או סכום לא תקינים", "error")
        return redirect("/payments/new")
    dups = pay_svc.find_duplicates(db, amt, d, reference)
    if dups and not force:
        flash(request, f"אזהרה: נמצאו {len(dups)} תשלומים דומים (אותו סכום/תאריך/אסמכתא). סמני 'לשמור בכל זאת' אם זה אינו כפילות.", "warning")
        child = db.get(Child, int(child_id)) if child_id else None
        return render(
            request,
            "payments/form.html",
            user,
            children=_children(db),
            child=child,
            open_charges=pay_svc.open_charges_for_child(db, child) if child else [],
            prefill={"paid_on": d.isoformat(), "amount": amt, "method": method, "payer_name": payer_name, "reference": reference, "bank_details": bank_details, "notes": notes},
            extraction=None,
            attachment=attachment,
            duplicates=dups,
            source=source,
        )
    if attachment and ("/" in attachment or ".." in attachment):
        attachment = ""
    p = pay_svc.create_payment(
        db,
        user,
        child_id=int(child_id) if child_id else None,
        paid_on=d,
        amount=amt,
        method=PaymentMethod(method),
        payer_name=payer_name.strip(),
        reference=reference.strip(),
        bank_details=bank_details.strip() if can(user, "payments.bank_details") else "",
        notes=notes.strip(),
        attachment_path=attachment,
        source=PaymentSource(source),
        verified=True,
    )
    allocs = pay_svc.auto_allocate(db, p, user) if auto_alloc else []
    db.commit()
    if p.child_id is None:
        flash(request, "התשלום נשמר ללא שיוך לילד – יש לשייך אותו", "warning")
    elif allocs:
        flash(request, f"התשלום נשמר ושויך ל-{len(allocs)} חיובים" + (f". נותרו {p.unallocated:.0f} ₪ ללא שיוך" if p.unallocated > 0.004 else ""))
    else:
        flash(request, "התשלום נשמר. לא נמצאו חיובים פתוחים לשיוך – ניתן לשייך ידנית.", "warning")
    return redirect(f"/payments/{p.id}")


def _payment(db: Session, pid: int) -> Payment:
    p = db.get(Payment, pid)
    if not p:
        raise HTTPException(404)
    return p


@router.get("/{pid}")
def payment_detail(request: Request, pid: int, db: Session = Depends(get_db), user=Depends(require_user)):
    p = _payment(db, pid)
    open_charges = pay_svc.open_charges_for_child(db, p.child) if p.child else []
    family = [(c, ch) for c, ch in pay_svc.family_open_charges(db, p.child) if c.id != p.child_id] if p.child else []
    return render(request, "payments/detail.html", user, p=p, children=_children(db), open_charges=open_charges, family_charges=family, show_bank=can(user, "payments.bank_details"))


@router.post("/{pid}")
def update_payment(request: Request, pid: int, child_id: str = Form(""), paid_on: str = Form(...), amount: str = Form(...), method: str = Form(...), payer_name: str = Form(""), reference: str = Form(""), bank_details: str = Form(""), notes: str = Form(""), db: Session = Depends(get_db), user=Depends(require("payments.add"))):
    p = _payment(db, pid)
    if p.receipts and any(r.status.value in ("issued", "sent") for r in p.receipts):
        flash(request, "לא ניתן לערוך תשלום שהופקה עליו קבלה", "error")
        return redirect(f"/payments/{pid}")
    before = audit.snapshot(p)
    new_child = int(child_id) if child_id else None
    if new_child != p.child_id:
        for a in list(p.allocations):
            pay_svc.remove_allocation(db, a, user)
    p.child_id = new_child
    p.paid_on = parse_date(paid_on) or p.paid_on
    p.amount = parse_money(amount) or p.amount
    p.method = PaymentMethod(method)
    p.payer_name = payer_name.strip()
    p.reference = reference.strip()
    if can(user, "payments.bank_details"):
        p.bank_details = bank_details.strip()
    p.notes = notes.strip()
    if p.allocated > float(p.amount) + 0.004:
        for a in list(p.allocations):
            pay_svc.remove_allocation(db, a, user)
    audit.log(db, user, "payment", p.id, "update", before=before, after=audit.snapshot(p))
    db.commit()
    flash(request, "התשלום עודכן")
    return redirect(f"/payments/{pid}")


@router.post("/{pid}/allocate")
def allocate(request: Request, pid: int, charge_id: int = Form(...), amount: str = Form(...), db: Session = Depends(get_db), user=Depends(require("payments.add"))):
    p = _payment(db, pid)
    ch = db.get(MonthlyCharge, charge_id)
    amt = parse_money(amount)
    if not ch or amt is None:
        flash(request, "נתונים לא תקינים", "error")
        return redirect(f"/payments/{pid}")
    try:
        pay_svc.allocate(db, p, ch, amt, user)
        db.commit()
        flash(request, "השיוך נשמר")
    except ValueError as e:
        db.rollback()
        flash(request, str(e), "error")
    return redirect(f"/payments/{pid}")


@router.post("/{pid}/auto-allocate")
def auto_allocate(request: Request, pid: int, db: Session = Depends(get_db), user=Depends(require("payments.add"))):
    p = _payment(db, pid)
    allocs = pay_svc.auto_allocate(db, p, user)
    db.commit()
    flash(request, f"שויכו {len(allocs)} חיובים" if allocs else "לא נמצאו חיובים פתוחים לשיוך", "success" if allocs else "warning")
    return redirect(f"/payments/{pid}")


@router.post("/allocations/{aid}/delete")
def delete_allocation(request: Request, aid: int, db: Session = Depends(get_db), user=Depends(require("payments.add"))):
    a = db.get(PaymentAllocation, aid)
    if not a:
        raise HTTPException(404)
    pid = a.payment_id
    if any(r.status.value in ("issued", "sent") and r.charge_id == a.charge_id for r in a.payment.receipts):
        flash(request, "לא ניתן לבטל שיוך שהופקה עליו קבלה", "error")
        return redirect(f"/payments/{pid}")
    pay_svc.remove_allocation(db, a, user)
    db.commit()
    flash(request, "השיוך בוטל")
    return redirect(f"/payments/{pid}")


@router.post("/{pid}/delete")
def delete_payment(request: Request, pid: int, db: Session = Depends(get_db), user=Depends(require("billing"))):
    p = _payment(db, pid)
    if p.receipts:
        flash(request, "לא ניתן למחוק תשלום שהוכנו עליו קבלות", "error")
        return redirect(f"/payments/{pid}")
    before = audit.snapshot(p)
    db.delete(p)
    audit.log(db, user, "payment", pid, "delete", before=before)
    db.commit()
    flash(request, "התשלום נמחק")
    return redirect("/payments")


@router.post("/{pid}/prepare-receipts")
def prepare_receipts(request: Request, pid: int, db: Session = Depends(get_db), user=Depends(require("receipts.approve"))):
    p = _payment(db, pid)
    try:
        created = rcpt_svc.prepare_for_payment(db, p, user)
        db.commit()
        flash(request, f"הוכנו {len(created)} טיוטות קבלה לבדיקה" if created else "לא נוצרו קבלות חדשות (כבר קיימות או אין שיוך)", "success" if created else "warning")
    except ValueError as e:
        db.rollback()
        flash(request, str(e), "error")
        return redirect(f"/payments/{pid}")
    return redirect("/receipts")


# ---- צילום מסך


@router.get("/upload/screenshot")
def upload_form(request: Request, db: Session = Depends(get_db), user=Depends(require("payments.add"))):
    return render(request, "payments/upload.html", user, ocr_available=ocr_svc.available())


@router.post("/upload/screenshot")
async def upload(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(require("payments.add"))):
    data = await file.read()
    if len(data) > config.MAX_UPLOAD_BYTES:
        flash(request, "הקובץ גדול מדי", "error")
        return redirect("/payments/upload/screenshot")
    ext = Path(file.filename or "").suffix.lower()
    if ext not in (".png", ".jpg", ".jpeg", ".webp", ".pdf"):
        flash(request, "יש להעלות תמונה (PNG/JPG/WEBP) או PDF", "error")
        return redirect("/payments/upload/screenshot")
    name = f"{date.today().isoformat()}-{secrets.token_hex(8)}{ext}"
    (config.UPLOAD_DIR / name).write_bytes(data)
    extraction = ocr_svc.extract(config.UPLOAD_DIR / name) if ext != ".pdf" else ocr_svc.Extraction(ok=False, error="פענוח אוטומטי נתמך לתמונות בלבד – יש להזין ידנית")
    prefill = {}
    dups = []
    if extraction.ok:
        f = extraction.fields
        prefill = {
            "paid_on": f.get("paid_on") or "",
            "amount": f.get("amount") or "",
            "payer_name": f.get("payer_name") or "",
            "reference": f.get("reference") or "",
            "method": f.get("method") or "bank_transfer",
            "bank_details": f.get("bank_details") or "",
            "notes": " | ".join(x for x in [f.get("recipient"), f.get("extra")] if x),
        }
        if extraction.unclear or extraction.confidence == "low":
            flash(request, "התמונה לא ברורה או שהפענוח אינו ודאי – יש לבדוק היטב את הפרטים או להזין ידנית", "warning")
        pd_, am = parse_date(prefill["paid_on"]), parse_money(str(prefill["amount"]))
        if pd_ and am:
            dups = pay_svc.find_duplicates(db, am, pd_, prefill["reference"])
    else:
        flash(request, extraction.error, "warning")
    # ניסיון לזהות את הילד לפי שם המשלם
    child = None
    if prefill.get("payer_name"):
        from ..models import Contact

        ct = db.query(Contact).filter(Contact.full_name.contains(prefill["payer_name"].split()[0])).first()
        if ct and ct.children:
            child = ct.children[0].child
    return render(
        request,
        "payments/form.html",
        user,
        children=_children(db),
        child=child,
        open_charges=pay_svc.open_charges_for_child(db, child) if child else [],
        prefill=prefill,
        extraction=extraction,
        attachment=name,
        duplicates=dups,
        source="screenshot",
    )


@router.get("/attachment/{name}")
def attachment(name: str, db: Session = Depends(get_db), user=Depends(require("payments.bank_details"))):
    path = config.UPLOAD_DIR / Path(name).name
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path)
