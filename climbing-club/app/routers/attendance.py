from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy.orm import Session

from .. import audit
from ..auth import require, require_user
from ..db import get_db
from ..models import Attendance, AttendanceStatus, ChargeOverride, ClubSession, SessionKind, SessionStatus
from ..services import attendance as att_svc
from ..services import calendar as cal_svc
from ..services.billing import is_month_closed
from ..web import flash, parse_date, parse_money, redirect, render

router = APIRouter(prefix="/attendance")


@router.get("")
def attendance_view(request: Request, on: str = "", session_id: int | None = None, year: int | None = None, month: int | None = None, db: Session = Depends(get_db), user=Depends(require_user)):
    current = db.get(ClubSession, session_id) if session_id else None
    d = current.date if current else (parse_date(on) or date.today())
    day_sessions = (
        db.query(ClubSession)
        .filter(ClubSession.date == d, ClubSession.status != SessionStatus.MOVED)
        .order_by(ClubSession.group_id)
        .all()
    )
    if current is None and day_sessions:
        current = day_sessions[0]
    rows = []
    if current:
        recs = att_svc.records_for(db, current)
        for c in att_svc.expected_children(db, current):
            rows.append({"child": c, "rec": recs.get(c.id)})
    pending = [s for s in cal_svc.past_sessions_needing_action(db) if s.date != d]
    if year and month:
        pending = [s for s in pending if (s.date.year, s.date.month) == (year, month)]
    return render(
        request,
        "attendance/day.html",
        user,
        on=d,
        day_sessions=day_sessions,
        current=current,
        rows=rows,
        pending=pending[:20],
        closed=is_month_closed(db, d.year, d.month),
    )


@router.post("/{sid}")
async def save(request: Request, sid: int, db: Session = Depends(get_db), user=Depends(require("attendance"))):
    s = db.get(ClubSession, sid)
    if not s:
        raise HTTPException(404)
    if is_month_closed(db, s.date.year, s.date.month):
        flash(request, "החודש סגור – יש לפתוח אותו מחדש לפני תיקון נוכחות", "error")
        return redirect(f"/attendance?session_id={s.id}")
    if s.status.is_cancelled or s.status == SessionStatus.MOVED:
        flash(request, "לא ניתן לדווח נוכחות למפגש שבוטל או הועבר", "error")
        return redirect(f"/attendance?session_id={s.id}")
    form = await request.form()
    statuses: dict[int, AttendanceStatus] = {}
    for key, val in form.multi_items():
        if key.startswith("status_"):
            try:
                statuses[int(key[7:])] = AttendanceStatus(val)
            except ValueError:
                continue
    n = att_svc.bulk_set(db, s, statuses, user)
    db.commit()
    missing = att_svc.missing_reports(db, s)
    if missing:
        flash(request, f"הדיווח נשמר ({n} שינויים). נותרו {len(missing)} ילדים ללא דיווח.", "warning")
    else:
        flash(request, f"הדיווח נשמר ({n} שינויים). הנוכחות למפגש הושלמה.")
    return redirect(f"/attendance?session_id={s.id}")


@router.post("/{sid}/child/{cid}/override")
def override(request: Request, sid: int, cid: int, charge_override: str = Form("default"), price_override: str = Form(""), note: str = Form(""), back: str = Form(""), db: Session = Depends(get_db), user=Depends(require("billing"))):
    """חריג חיוב ברמת מפגש בודד לילד: לחייב / לא לחייב / מחיר שונה."""
    s = db.get(ClubSession, sid)
    if not s:
        raise HTTPException(404)
    if is_month_closed(db, s.date.year, s.date.month):
        flash(request, "החודש סגור", "error")
        return redirect(back or f"/attendance?session_id={sid}")
    rec = db.query(Attendance).filter_by(session_id=sid, child_id=cid).first()
    if rec is None:
        from ..models import Child

        child = db.get(Child, cid)
        if not child:
            raise HTTPException(404)
        rec = att_svc.set_status(db, s, child, AttendanceStatus.UNREPORTED, user)
    before = audit.snapshot(rec)
    rec.charge_override = ChargeOverride(charge_override)
    rec.price_override = parse_money(price_override)
    rec.note = note.strip()
    audit.log(db, user, "attendance", rec.id, "override", before=before, after=audit.snapshot(rec))
    db.commit()
    flash(request, "החריג נשמר. יש לחשב מחדש את החיוב החודשי.")
    return redirect(back or f"/attendance?session_id={sid}")
