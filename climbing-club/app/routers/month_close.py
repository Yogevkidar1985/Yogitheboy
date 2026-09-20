from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from ..auth import require, require_user
from ..db import get_db
from ..services import month_close as mc_svc
from ..web import flash, prev_next, redirect, render, ym_from_query

router = APIRouter(prefix="/month-close")


@router.get("")
def view(request: Request, year: int | None = None, month: int | None = None, db: Session = Depends(get_db), user=Depends(require_user)):
    y, m = ym_from_query(year, month)
    s = mc_svc.summary(db, y, m)
    return render(request, "month_close.html", user, s=s, year=y, month=m, prev_next=prev_next(y, m))


@router.post("/close")
def close(request: Request, year: int = Form(...), month: int = Form(...), force: bool = Form(False), db: Session = Depends(get_db), user=Depends(require("month.close"))):
    try:
        mc_svc.close_month(db, year, month, user, force=force)
        db.commit()
        flash(request, "החודש נסגר. החיובים קפואים ונשמרה תמונת מצב.")
    except ValueError as e:
        db.rollback()
        flash(request, str(e), "error")
    return redirect(f"/month-close?year={year}&month={month}")


@router.post("/reopen")
def reopen(request: Request, year: int = Form(...), month: int = Form(...), reason: str = Form(...), db: Session = Depends(get_db), user=Depends(require("month.close"))):
    try:
        mc_svc.reopen_month(db, year, month, user, reason)
        db.commit()
        flash(request, "החודש נפתח מחדש – השינוי תועד")
    except ValueError as e:
        db.rollback()
        flash(request, str(e), "error")
    return redirect(f"/month-close?year={year}&month={month}")
