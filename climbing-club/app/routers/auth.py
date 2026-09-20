from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from .. import audit
from ..auth import get_current_user, hash_password, verify_password
from ..db import get_db
from ..models import Role, User
from ..web import flash, redirect, render

router = APIRouter()


@router.get("/setup")
def setup_form(request: Request, db: Session = Depends(get_db)):
    if db.query(User.id).first() is not None:
        return redirect("/")
    return render(request, "setup.html")


@router.post("/setup")
def setup_submit(
    request: Request,
    display_name: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    password2: str = Form(...),
    db: Session = Depends(get_db),
):
    if db.query(User.id).first() is not None:
        return redirect("/")
    if password != password2:
        flash(request, "הסיסמאות אינן תואמות", "error")
        return redirect("/setup")
    if len(password) < 8:
        flash(request, "הסיסמה חייבת להכיל לפחות 8 תווים", "error")
        return redirect("/setup")
    u = User(username=username.strip().lower(), display_name=display_name.strip(), password_hash=hash_password(password), role=Role.ADMIN)
    db.add(u)
    db.commit()
    request.session["user_id"] = u.id
    flash(request, f"ברוכה הבאה, {u.display_name}. המערכת הוקמה בהצלחה.")
    return redirect("/")


@router.get("/login")
def login_form(request: Request, user=Depends(get_current_user)):
    if user:
        return redirect("/")
    return render(request, "login.html")


@router.post("/login")
def login_submit(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    u = db.query(User).filter_by(username=username.strip().lower()).first()
    if not u or not u.is_active or not verify_password(password, u.password_hash):
        flash(request, "שם משתמש או סיסמה שגויים", "error")
        return redirect("/login")
    request.session.clear()
    request.session["user_id"] = u.id
    audit.log(db, u, "user", u.id, "login")
    db.commit()
    nxt = request.session.pop("next", None) or "/"
    return redirect(nxt if nxt.startswith("/") else "/")


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return redirect("/login")
