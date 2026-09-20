"""לוח מפגשים: יצירה חודשית, ביטולים, העברות, מפגשים חריגים וזיהוי התנגשויות."""
from __future__ import annotations

import calendar as _cal
from datetime import date, datetime

from sqlalchemy import and_
from sqlalchemy.orm import Session

from .. import audit
from ..models import Attendance, ClubSession, Group, SessionKind, SessionStatus, User

WEEKDAY_NAMES = {6: "ראשון", 0: "שני", 1: "שלישי", 2: "רביעי", 3: "חמישי", 4: "שישי", 5: "שבת"}
MONTH_NAMES = {
    1: "ינואר", 2: "פברואר", 3: "מרץ", 4: "אפריל", 5: "מאי", 6: "יוני",
    7: "יולי", 8: "אוגוסט", 9: "ספטמבר", 10: "אוקטובר", 11: "נובמבר", 12: "דצמבר",
}
STATUS_LABELS = {
    SessionStatus.PLANNED: "מתוכנן",
    SessionStatus.HELD: "התקיים",
    SessionStatus.PENDING_ATTENDANCE: "ממתין להשלמת נוכחות",
    SessionStatus.CANCELLED_HOLIDAY: "בוטל – חג",
    SessionStatus.CANCELLED_ADMIN: "בוטל – מנהלת",
    SessionStatus.CANCELLED_OTHER: "בוטל – סיבה אחרת",
    SessionStatus.MOVED: "הועבר",
}


def month_range(year: int, month: int) -> tuple[date, date]:
    last = _cal.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def month_sessions(db: Session, year: int, month: int, kind: SessionKind | None = SessionKind.REGULAR) -> list[ClubSession]:
    first, last = month_range(year, month)
    q = db.query(ClubSession).filter(ClubSession.date >= first, ClubSession.date <= last)
    if kind is not None:
        q = q.filter(ClubSession.kind == kind)
    return q.order_by(ClubSession.date, ClubSession.group_id).all()


def generate_month(db: Session, year: int, month: int, user: User | None = None) -> list[ClubSession]:
    """יוצר מפגשים מתוכננים לכל קבוצה פעילה לפי יום הפעילות הקבוע. לא נוגע במפגשים קיימים."""
    first, last = month_range(year, month)
    created: list[ClubSession] = []
    groups = db.query(Group).filter(Group.is_active.is_(True)).all()
    existing = {
        (s.date, s.group_id)
        for s in month_sessions(db, year, month)
    }
    for g in groups:
        d = first
        while d <= last:
            if d.weekday() == g.weekday and (d, g.id) not in existing:
                s = ClubSession(
                    date=d,
                    group_id=g.id,
                    start_time=g.start_time,
                    status=SessionStatus.PLANNED,
                    created_by=user.display_name if user else "",
                )
                db.add(s)
                created.append(s)
            d = date.fromordinal(d.toordinal() + 1)
    db.flush()
    for s in created:
        audit.log(db, user, "session", s.id, "generate", after=audit.snapshot(s))
    return created


def add_extra_session(
    db: Session, group: Group, on: date, reason: str, user: User | None, start_time: str = ""
) -> ClubSession:
    """מפגש בתאריך חריג (למשל יום שלישי במקום רביעי)."""
    if find_conflict(db, on, group.id):
        raise ValueError("כבר קיים מפגש לקבוצה זו בתאריך המבוקש")
    s = ClubSession(
        date=on,
        group_id=group.id,
        start_time=start_time or group.start_time,
        status=SessionStatus.PLANNED,
        is_extra=True,
        reason=reason,
        created_by=user.display_name if user else "",
    )
    db.add(s)
    db.flush()
    audit.log(db, user, "session", s.id, "add_extra", after=audit.snapshot(s))
    return s


def find_conflict(db: Session, on: date, group_id: int | None, exclude_id: int | None = None) -> ClubSession | None:
    q = db.query(ClubSession).filter(
        and_(ClubSession.date == on, ClubSession.group_id == group_id, ClubSession.kind == SessionKind.REGULAR)
    )
    if exclude_id:
        q = q.filter(ClubSession.id != exclude_id)
    return q.first()


def _touch(s: ClubSession, user: User | None) -> None:
    s.changed_by = user.display_name if user else ""
    s.changed_at = datetime.now()


def cancel_session(db: Session, s: ClubSession, status: SessionStatus, reason: str, user: User | None) -> None:
    if not status.is_cancelled:
        raise ValueError("סטטוס ביטול לא חוקי")
    before = audit.snapshot(s)
    s.status = status
    s.reason = reason
    _touch(s, user)
    audit.log(db, user, "session", s.id, "cancel", before=before, after=audit.snapshot(s))


def move_session(db: Session, s: ClubSession, new_date: date, reason: str, user: User | None) -> ClubSession:
    """מסמן את המפגש המקורי כ'הועבר' ויוצר מפגש חדש. הנוכחות והחיוב לפי המפגש החדש בלבד."""
    if s.status == SessionStatus.MOVED:
        raise ValueError("המפגש כבר הועבר")
    if find_conflict(db, new_date, s.group_id):
        raise ValueError("כבר קיים מפגש לקבוצה זו בתאריך היעד")
    before = audit.snapshot(s)
    new = ClubSession(
        date=new_date,
        group_id=s.group_id,
        start_time=s.start_time,
        status=SessionStatus.PLANNED,
        is_extra=True,
        original_date=s.date,
        reason=reason,
        created_by=user.display_name if user else "",
    )
    db.add(new)
    db.flush()
    s.status = SessionStatus.MOVED
    s.moved_to_id = new.id
    s.reason = reason
    _touch(s, user)
    # דיווחי נוכחות שנרשמו בטעות למפגש המקורי אינם רלוונטיים
    for a in list(s.attendance):
        db.delete(a)
    audit.log(db, user, "session", s.id, "move", before=before, after=audit.snapshot(s))
    audit.log(db, user, "session", new.id, "create_from_move", after=audit.snapshot(new))
    return new


def cancel_range(db: Session, start: date, end: date, status: SessionStatus, reason: str, user: User | None) -> list[ClubSession]:
    """ביטול מרוכז של כל המפגשים המתוכננים בטווח תאריכים (למשל שבוע חג). מפגשים שהתקיימו אינם נוגעים."""
    if end < start:
        raise ValueError("תאריך הסיום קודם לתאריך ההתחלה")
    out = []
    for s in (
        db.query(ClubSession)
        .filter(ClubSession.date >= start, ClubSession.date <= end, ClubSession.status == SessionStatus.PLANNED, ClubSession.kind == SessionKind.REGULAR)
        .all()
    ):
        cancel_session(db, s, status, reason, user)
        out.append(s)
    return out


def restore_session(db: Session, s: ClubSession, user: User | None) -> None:
    """מחזיר מפגש שבוטל למצב מתוכנן."""
    if s.status == SessionStatus.MOVED:
        raise ValueError("לא ניתן לשחזר מפגש שהועבר – יש למחוק את המפגש החדש")
    before = audit.snapshot(s)
    s.status = SessionStatus.PLANNED
    s.reason = ""
    _touch(s, user)
    audit.log(db, user, "session", s.id, "restore", before=before, after=audit.snapshot(s))


def mark_held(db: Session, s: ClubSession, user: User | None) -> None:
    before = audit.snapshot(s)
    s.status = SessionStatus.PENDING_ATTENDANCE
    _touch(s, user)
    audit.log(db, user, "session", s.id, "mark_held", before=before, after=audit.snapshot(s))


def refresh_status(db: Session, s: ClubSession) -> None:
    """מעדכן בין 'ממתין להשלמת נוכחות' ל'התקיים' לפי מצב הדיווח."""
    if not s.status.counts_as_held:
        return
    from .attendance import missing_reports

    s.status = SessionStatus.PENDING_ATTENDANCE if missing_reports(db, s) else SessionStatus.HELD


def delete_session(db: Session, s: ClubSession, user: User | None) -> None:
    if s.attendance and any(a.status.value != "unreported" for a in s.attendance):
        raise ValueError("לא ניתן למחוק מפגש שדווחה בו נוכחות. אפשר לבטל אותו במקום.")
    before = audit.snapshot(s)
    origin = db.query(ClubSession).filter(ClubSession.moved_to_id == s.id).first()
    if origin:
        origin.status = SessionStatus.PLANNED
        origin.moved_to_id = None
        _touch(origin, user)
    db.delete(s)
    audit.log(db, user, "session", before.get("id"), "delete", before=before)


def duplicates_in_month(db: Session, year: int, month: int) -> list[tuple[ClubSession, ClubSession]]:
    """זיהוי כפילות: שני מפגשים לאותה קבוצה באותו יום (יכול לקרות רק אם נוצרו מחוץ למנגנון)."""
    seen: dict[tuple[date, int | None], ClubSession] = {}
    dups = []
    for s in month_sessions(db, year, month):
        key = (s.date, s.group_id)
        if key in seen:
            dups.append((seen[key], s))
        else:
            seen[key] = s
    return dups


def past_sessions_needing_action(db: Session, today: date | None = None) -> list[ClubSession]:
    """מפגשים שתאריכם עבר ועדיין 'מתוכנן' או 'ממתין להשלמת נוכחות'."""
    today = today or date.today()
    return (
        db.query(ClubSession)
        .filter(
            ClubSession.date <= today,
            ClubSession.status.in_([SessionStatus.PLANNED, SessionStatus.PENDING_ATTENDANCE]),
        )
        .order_by(ClubSession.date)
        .all()
    )
