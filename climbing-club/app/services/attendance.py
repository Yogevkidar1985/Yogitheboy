"""דיווח נוכחות: רשימת הילדים הצפויים במפגש, סימון מהיר ותיקון עם תיעוד."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from .. import audit
from ..models import (
    Attendance,
    AttendanceStatus,
    Child,
    ChildStatus,
    ClubSession,
    IntroSession,
    Membership,
    SessionKind,
    User,
)

STATUS_LABELS = {
    AttendanceStatus.PRESENT: "נכח",
    AttendanceStatus.ABSENT: "החסיר",
    AttendanceStatus.UNREPORTED: "לא דווח",
}


def _child_active_on(child: Child, on) -> bool:
    """ילד נחשב פעיל במפגש אם הצטרף לפני התאריך ולא סיים פעילות לפניו."""
    if child.joined_on and on < child.joined_on:
        return False
    if child.left_on and on > child.left_on:
        return False
    if child.status == ChildStatus.LEFT and not child.left_on:
        return False
    return True


def expected_children(db: Session, s: ClubSession) -> list[Child]:
    """הילדים המשויכים למפגש: חברי הקבוצה בתאריך המפגש + ילדים שכבר דווחו בו."""
    if s.kind == SessionKind.INTRO:
        intro = db.query(IntroSession).filter(IntroSession.session_id == s.id).all()
        return [i.child for i in intro]
    kids: dict[int, Child] = {}
    if s.group_id:
        for m in db.query(Membership).filter(Membership.group_id == s.group_id).all():
            if m.covers(s.date) and _child_active_on(m.child, s.date):
                kids[m.child_id] = m.child
    for a in s.attendance:
        kids[a.child_id] = a.child
    return sorted(kids.values(), key=lambda c: c.full_name)


def records_for(db: Session, s: ClubSession) -> dict[int, Attendance]:
    return {a.child_id: a for a in s.attendance}


def missing_reports(db: Session, s: ClubSession) -> list[Child]:
    recs = records_for(db, s)
    out = []
    for c in expected_children(db, s):
        a = recs.get(c.id)
        if a is None or a.status == AttendanceStatus.UNREPORTED:
            out.append(c)
    return out


def set_status(
    db: Session,
    s: ClubSession,
    child: Child,
    status: AttendanceStatus,
    user: User | None,
    note: str | None = None,
) -> Attendance:
    """קובע/מעדכן דיווח לילד במפגש. כל שינוי נרשם ביומן."""
    rec = db.query(Attendance).filter_by(session_id=s.id, child_id=child.id).first()
    if rec is None:
        rec = Attendance(session=s, child=child, status=AttendanceStatus.UNREPORTED)  # שיוך דרך הקשר מעדכן את האוספים בזיכרון
        db.add(rec)
        db.flush()
        before = None
    else:
        before = audit.snapshot(rec)
    changed = rec.status != status or (note is not None and note != rec.note)
    rec.status = status
    if note is not None:
        rec.note = note
    if changed or before is None:
        rec.reported_at = datetime.now()
        rec.reported_by = user.display_name if user else ""
        audit.log(db, user, "attendance", rec.id, "update" if before else "create", before=before, after=audit.snapshot(rec))
    return rec


def bulk_set(db: Session, s: ClubSession, statuses: dict[int, AttendanceStatus], user: User | None) -> int:
    """שמירת טופס נוכחות שלם. מחזיר את מספר הרשומות ששונו."""
    from .calendar import mark_held, refresh_status

    if s.status.value == "planned":
        mark_held(db, s, user)
    children = {c.id: c for c in expected_children(db, s)}
    n = 0
    for cid, st in statuses.items():
        child = children.get(cid) or db.get(Child, cid)
        if child is None:
            continue
        before = db.query(Attendance).filter_by(session_id=s.id, child_id=cid).first()
        prev = before.status if before else None
        set_status(db, s, child, st, user)
        if prev != st:
            n += 1
    db.flush()
    refresh_status(db, s)
    return n


def child_history(db: Session, child: Child) -> list[Attendance]:
    return (
        db.query(Attendance)
        .join(ClubSession)
        .filter(Attendance.child_id == child.id)
        .order_by(ClubSession.date.desc())
        .all()
    )
