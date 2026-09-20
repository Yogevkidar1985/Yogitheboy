from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .. import audit, config
from ..auth import hash_password, require, require_user
from ..db import get_db
from ..models import AuditLog, Child, MonthlyCharge, Payment, Role, User
from ..services import backup as backup_svc
from ..services import settings as settings_svc
from ..web import flash, redirect, render

router = APIRouter(prefix="/settings")


@router.get("")
def settings_view(request: Request, db: Session = Depends(get_db), user=Depends(require_user)):
    return render(request, "settings/index.html", user, values=settings_svc.get_all(db), labels=settings_svc.LABELS, provider=config.RECEIPT_PROVIDER, ocr=bool(config.ANTHROPIC_API_KEY))


@router.post("")
async def settings_save(request: Request, db: Session = Depends(get_db), user=Depends(require("settings"))):
    form = await request.form()
    before = settings_svc.get_all(db)
    for key in settings_svc.DEFAULTS:
        if key in form:
            settings_svc.set_(db, key, str(form[key]).strip() if key not in ("message_template",) else str(form[key]))
    audit.log(db, user, "settings", None, "update", before=before, after=settings_svc.get_all(db))
    db.commit()
    flash(request, "ההגדרות נשמרו")
    return redirect("/settings")


@router.get("/users")
def users(request: Request, db: Session = Depends(get_db), user=Depends(require("users"))):
    return render(request, "settings/users.html", user, users=db.query(User).order_by(User.id).all())


@router.post("/users")
def create_user(request: Request, username: str = Form(...), display_name: str = Form(...), password: str = Form(...), role: str = Form(...), db: Session = Depends(get_db), user=Depends(require("users"))):
    if len(password) < 8:
        flash(request, "הסיסמה חייבת להכיל לפחות 8 תווים", "error")
        return redirect("/settings/users")
    if db.query(User).filter_by(username=username.strip().lower()).first():
        flash(request, "שם המשתמש תפוס", "error")
        return redirect("/settings/users")
    u = User(username=username.strip().lower(), display_name=display_name.strip(), password_hash=hash_password(password), role=Role(role))
    db.add(u)
    db.flush()
    audit.log(db, user, "user", u.id, "create", after={"username": u.username, "role": u.role.value})
    db.commit()
    flash(request, "המשתמש נוצר")
    return redirect("/settings/users")


@router.post("/users/{uid}")
def update_user(request: Request, uid: int, display_name: str = Form(...), role: str = Form(...), is_active: bool = Form(False), password: str = Form(""), db: Session = Depends(get_db), user=Depends(require("users"))):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404)
    if u.id == user.id and (not is_active or Role(role) != Role.ADMIN):
        flash(request, "לא ניתן להסיר את ההרשאה או להשבית את המשתמש שלך", "error")
        return redirect("/settings/users")
    before = {"display_name": u.display_name, "role": u.role.value, "is_active": u.is_active}
    u.display_name, u.role, u.is_active = display_name.strip(), Role(role), is_active
    if password:
        if len(password) < 8:
            flash(request, "הסיסמה חייבת להכיל לפחות 8 תווים", "error")
            return redirect("/settings/users")
        u.password_hash = hash_password(password)
    audit.log(db, user, "user", u.id, "update", before=before, after={"display_name": u.display_name, "role": u.role.value, "is_active": u.is_active, "password_changed": bool(password)})
    db.commit()
    flash(request, "המשתמש עודכן")
    return redirect("/settings/users")


@router.get("/audit")
def audit_view(request: Request, entity: str = "", entity_id: int | None = None, db: Session = Depends(get_db), user=Depends(require("audit"))):
    q = db.query(AuditLog).order_by(AuditLog.at.desc())
    if entity:
        q = q.filter(AuditLog.entity == entity)
    if entity_id:
        q = q.filter(AuditLog.entity_id == entity_id)
    return render(request, "settings/audit.html", user, rows=q.limit(300).all(), entity=entity, entity_id=entity_id)


@router.get("/backup")
def backup_view(request: Request, db: Session = Depends(get_db), user=Depends(require("users"))):
    return render(request, "settings/backup.html", user, backups=[p.name for p in backup_svc.list_backups()])


@router.post("/backup")
def backup_create(request: Request, user=Depends(require("users"))):
    try:
        p = backup_svc.create_backup()
        flash(request, f"נוצר גיבוי: {p.name}")
    except RuntimeError as e:
        flash(request, str(e), "error")
    return redirect("/settings/backup")


@router.post("/restore")
def backup_restore(request: Request, name: str = Form(...), confirm: bool = Form(False), db: Session = Depends(get_db), user=Depends(require("users"))):
    if not confirm:
        flash(request, "יש לאשר את השחזור במפורש", "error")
        return redirect("/settings/backup")
    try:
        safety = backup_svc.restore_backup(name)
        audit.log(db, user, "backup", None, "restore", note=f"שוחזר {name}; גיבוי בטיחות {safety.name}")
        db.commit()
        flash(request, f"המסד שוחזר מ-{name}. גיבוי בטיחות של המצב הקודם: {safety.name}")
    except (RuntimeError, FileNotFoundError) as e:
        flash(request, str(e), "error")
    return redirect("/settings/backup")


@router.get("/reports")
def reports(request: Request, year: int | None = None, db: Session = Depends(get_db), user=Depends(require("billing"))):
    from datetime import date

    y = year or date.today().year
    charges = db.query(MonthlyCharge).filter_by(year=y).all()
    by_child: dict[int, dict] = {}
    for c in charges:
        row = by_child.setdefault(c.child_id, {"child": c.child, "months": {}, "amount": 0.0, "paid": 0.0, "held": 0, "attended": 0})
        row["months"][c.month] = c
        row["amount"] += float(c.amount)
        row["paid"] += c.paid
        row["held"] += c.sessions_held
        row["attended"] += c.sessions_attended
    rows = sorted(by_child.values(), key=lambda r: r["child"].full_name)
    monthly = {m: sum(float(c.amount) for c in charges if c.month == m) for m in range(1, 13)}
    monthly_paid = {m: sum(c.paid for c in charges if c.month == m) for m in range(1, 13)}
    return render(request, "settings/reports.html", user, year=y, rows=rows, monthly=monthly, monthly_paid=monthly_paid)


@router.get("/reports/export.csv")
def export_csv(year: int, month: int | None = None, db: Session = Depends(get_db), user=Depends(require("billing"))):
    q = db.query(MonthlyCharge).filter_by(year=year)
    if month:
        q = q.filter_by(month=month)
    buf = io.StringIO()
    buf.write("﻿")
    w = csv.writer(buf)
    w.writerow(["שנה", "חודש", "ילד", "שיטת חיוב", "מפגשים שהתקיימו", "נכח", "החסיר", "בוטלו", "מחיר למפגש", "התאמות", "סכום לחיוב", "שולם", "יתרה", "סטטוס"])
    for c in q.join(Child).order_by(MonthlyCharge.month, Child.full_name).all():
        w.writerow([c.year, c.month, c.child.full_name, c.method.value, c.sessions_held, c.sessions_attended, c.sessions_absent, c.sessions_cancelled, float(c.price_per_session), float(c.adjustments_total), float(c.amount), c.paid, c.balance, c.status.value])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f"attachment; filename=charges-{year}.csv"})
