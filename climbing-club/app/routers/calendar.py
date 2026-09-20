from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy.orm import Session

from .. import audit
from ..auth import require, require_user
from ..db import get_db
from ..models import ClubSession, Group, SessionStatus
from ..services import calendar as cal_svc
from ..services.attendance import expected_children, missing_reports
from ..web import flash, parse_date, prev_next, redirect, render, ym_from_query

router = APIRouter()


@router.get("/calendar")
def calendar_view(request: Request, year: int | None = None, month: int | None = None, view: str = "", week: str = "", db: Session = Depends(get_db), user=Depends(require_user)):
    from datetime import date as _date, timedelta

    y, m = ym_from_query(year, month)
    if view not in ("month", "week", "list"):
        view = "week" if "Mobi" in (request.headers.get("user-agent") or "") else "month"
    if view == "list":
        today = _date.today()
        upcoming = (
            db.query(ClubSession).filter(ClubSession.date >= today, ClubSession.status != SessionStatus.MOVED).order_by(ClubSession.date, ClubSession.group_id).limit(30).all()
        )
        stale = cal_svc.past_sessions_needing_action(db)
        groups = db.query(Group).order_by(Group.weekday).all()
        return render(request, "calendar/list.html", user, view=view, year=y, month=m, upcoming=[(s, len(expected_children(db, s))) for s in upcoming], stale=stale, groups=groups)
    if view == "week":
        start = parse_date(week) or _date.today()
        start = start - timedelta(days=(start.weekday() + 1) % 7)  # יום ראשון
        days = [start + timedelta(days=i) for i in range(7)]
        sess = db.query(ClubSession).filter(ClubSession.date >= days[0], ClubSession.date <= days[-1]).order_by(ClubSession.date, ClubSession.group_id).all()
        by_day = {d: [s for s in sess if s.date == d] for d in days}
        groups = db.query(Group).order_by(Group.weekday).all()
        return render(request, "calendar/week.html", user, view=view, year=days[0].year, month=days[0].month, days=days, by_day=by_day, groups=groups, prev_week=(days[0] - timedelta(days=7)).isoformat(), next_week=(days[0] + timedelta(days=7)).isoformat(), today=_date.today(), missing={s.id: len(missing_reports(db, s)) for s in sess if s.status.counts_as_held})
    sessions = cal_svc.month_sessions(db, y, m, kind=None)
    groups = db.query(Group).order_by(Group.weekday).all()
    rows = []
    for s in sessions:
        rows.append({"s": s, "expected": len(expected_children(db, s)), "missing": len(missing_reports(db, s)) if s.status.counts_as_held else 0})
    changes = [s for s in sessions if s.status != SessionStatus.PLANNED and s.status != SessionStatus.HELD or s.is_extra]
    return render(
        request,
        "calendar/month.html",
        user,
        view=view,
        year=y,
        month=m,
        rows=rows,
        groups=groups,
        changes=changes,
        dups=cal_svc.duplicates_in_month(db, y, m),
        prev_next=prev_next(y, m),
    )


@router.post("/calendar/generate")
def generate(request: Request, year: int = Form(...), month: int = Form(...), db: Session = Depends(get_db), user=Depends(require("calendar.edit"))):
    created = cal_svc.generate_month(db, year, month, user)
    db.commit()
    flash(request, f"נוצרו {len(created)} מפגשים מתוכננים לחודש {cal_svc.MONTH_NAMES[month]}. עברי על הלוח ואשרי את המועדים.")
    return redirect(f"/calendar?year={year}&month={month}")


@router.post("/calendar/extra")
def extra(request: Request, group_id: int = Form(...), on: str = Form(...), reason: str = Form(""), start_time: str = Form(""), db: Session = Depends(get_db), user=Depends(require("calendar.edit"))):
    g = db.get(Group, group_id)
    d = parse_date(on)
    if not g or not d:
        flash(request, "קבוצה או תאריך לא תקינים", "error")
        return redirect("/calendar")
    try:
        cal_svc.add_extra_session(db, g, d, reason, user, start_time)
        db.commit()
        flash(request, f"נוסף מפגש חריג ל{g.name} בתאריך {d.strftime('%d/%m/%Y')}")
    except ValueError as e:
        db.rollback()
        flash(request, str(e), "error")
    return redirect(f"/calendar?year={d.year}&month={d.month}")


@router.post("/calendar/cancel-range")
def cancel_range(request: Request, start: str = Form(...), end: str = Form(...), status: str = Form("cancelled_holiday"), reason: str = Form(""), db: Session = Depends(get_db), user=Depends(require("calendar.edit"))):
    a, b = parse_date(start), parse_date(end)
    if not a or not b:
        flash(request, "תאריכים לא תקינים", "error")
        return redirect("/calendar")
    try:
        done = cal_svc.cancel_range(db, a, b, SessionStatus(status), reason, user)
        db.commit()
        flash(request, f"בוטלו {len(done)} מפגשים מתוכננים בין {a.strftime('%d/%m')} ל-{b.strftime('%d/%m')}")
    except ValueError as e:
        db.rollback()
        flash(request, str(e), "error")
    return redirect(f"/calendar?year={a.year}&month={a.month}")


def _session(db: Session, sid: int) -> ClubSession:
    s = db.get(ClubSession, sid)
    if not s:
        raise HTTPException(404)
    return s


@router.post("/calendar/{sid}/cancel")
def cancel(request: Request, sid: int, status: str = Form(...), reason: str = Form(""), db: Session = Depends(get_db), user=Depends(require("calendar.edit"))):
    s = _session(db, sid)
    try:
        cal_svc.cancel_session(db, s, SessionStatus(status), reason, user)
        db.commit()
        flash(request, "המפגש בוטל ותועד")
    except ValueError as e:
        db.rollback()
        flash(request, str(e), "error")
    return redirect(f"/calendar?year={s.date.year}&month={s.date.month}")


@router.post("/calendar/{sid}/move")
def move(request: Request, sid: int, new_date: str = Form(...), reason: str = Form(""), db: Session = Depends(get_db), user=Depends(require("calendar.edit"))):
    s = _session(db, sid)
    d = parse_date(new_date)
    if not d:
        flash(request, "תאריך יעד לא תקין", "error")
        return redirect(f"/calendar?year={s.date.year}&month={s.date.month}")
    try:
        new = cal_svc.move_session(db, s, d, reason, user)
        db.commit()
        flash(request, f"המפגש הועבר ל-{d.strftime('%d/%m/%Y')}. המפגש המקורי סומן כ'הועבר' ואינו מחויב.")
    except ValueError as e:
        db.rollback()
        flash(request, str(e), "error")
    return redirect(f"/calendar?year={s.date.year}&month={s.date.month}")


@router.post("/calendar/{sid}/restore")
def restore(request: Request, sid: int, db: Session = Depends(get_db), user=Depends(require("calendar.edit"))):
    s = _session(db, sid)
    try:
        cal_svc.restore_session(db, s, user)
        db.commit()
        flash(request, "המפגש הוחזר למצב מתוכנן")
    except ValueError as e:
        db.rollback()
        flash(request, str(e), "error")
    return redirect(f"/calendar?year={s.date.year}&month={s.date.month}")


@router.post("/calendar/{sid}/held")
def held(request: Request, sid: int, db: Session = Depends(get_db), user=Depends(require("attendance"))):
    s = _session(db, sid)
    cal_svc.mark_held(db, s, user)
    cal_svc.refresh_status(db, s)
    db.commit()
    return redirect(f"/attendance?session_id={s.id}")


@router.post("/calendar/{sid}/delete")
def delete(request: Request, sid: int, db: Session = Depends(get_db), user=Depends(require("calendar.edit"))):
    s = _session(db, sid)
    y, m = s.date.year, s.date.month
    try:
        cal_svc.delete_session(db, s, user)
        db.commit()
        flash(request, "המפגש נמחק")
    except ValueError as e:
        db.rollback()
        flash(request, str(e), "error")
    return redirect(f"/calendar?year={y}&month={m}")


@router.post("/calendar/{sid}/note")
def note(request: Request, sid: int, notes: str = Form(""), start_time: str = Form(""), db: Session = Depends(get_db), user=Depends(require("calendar.edit"))):
    s = _session(db, sid)
    before = audit.snapshot(s)
    s.notes = notes.strip()
    if start_time:
        s.start_time = start_time
    audit.log(db, user, "session", s.id, "note", before=before, after=audit.snapshot(s))
    db.commit()
    return redirect(f"/calendar?year={s.date.year}&month={s.date.month}")


# ---- קבוצות


@router.get("/groups")
def groups(request: Request, db: Session = Depends(get_db), user=Depends(require_user)):
    return render(request, "calendar/groups.html", user, groups=db.query(Group).order_by(Group.weekday).all())


@router.post("/groups")
def create_group(request: Request, name: str = Form(...), weekday: int = Form(...), start_time: str = Form("16:00"), notes: str = Form(""), db: Session = Depends(get_db), user=Depends(require("calendar.edit"))):
    g = Group(name=name.strip(), weekday=weekday, start_time=start_time, notes=notes.strip())
    db.add(g)
    db.flush()
    audit.log(db, user, "group", g.id, "create", after=audit.snapshot(g))
    db.commit()
    flash(request, "הקבוצה נוצרה")
    return redirect("/groups")


@router.post("/groups/{gid}")
def update_group(request: Request, gid: int, name: str = Form(...), weekday: int = Form(...), start_time: str = Form("16:00"), is_active: bool = Form(False), notes: str = Form(""), db: Session = Depends(get_db), user=Depends(require("calendar.edit"))):
    g = db.get(Group, gid)
    if not g:
        raise HTTPException(404)
    before = audit.snapshot(g)
    g.name, g.weekday, g.start_time, g.is_active, g.notes = name.strip(), weekday, start_time, is_active, notes.strip()
    audit.log(db, user, "group", g.id, "update", before=before, after=audit.snapshot(g))
    db.commit()
    flash(request, "הקבוצה עודכנה")
    return redirect("/groups")
