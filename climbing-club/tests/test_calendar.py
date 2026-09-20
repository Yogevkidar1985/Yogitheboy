from datetime import date

import pytest

from app.models import SessionStatus
from app.services import calendar as cal


def test_generate_month_creates_sessions_only_on_group_weekdays(db, user, groups):
    created = cal.generate_month(db, 2026, 9, user)
    # ספטמבר 2026: 4 ימי ראשון (6,13,20,27) + 5 ימי רביעי (2,9,16,23,30)
    assert len(created) == 9
    assert all(s.date.weekday() == s.group.weekday for s in created)
    # הרצה חוזרת אינה יוצרת כפילויות
    assert cal.generate_month(db, 2026, 9, user) == []


def test_cancel_and_restore(db, user, groups):
    s = cal.generate_month(db, 2026, 9, user)[0]
    cal.cancel_session(db, s, SessionStatus.CANCELLED_HOLIDAY, "חג", user)
    assert s.status.is_cancelled and s.reason == "חג" and s.changed_by == "בודקת"
    cal.restore_session(db, s, user)
    assert s.status == SessionStatus.PLANNED


def test_move_session_creates_new_and_marks_original(db, user, groups):
    sun, wed = groups
    sessions = cal.generate_month(db, 2026, 9, user)
    original = next(s for s in sessions if s.date == date(2026, 9, 30))
    new = cal.move_session(db, original, date(2026, 9, 29), "חול המועד", user)
    assert original.status == SessionStatus.MOVED and original.moved_to_id == new.id
    assert new.date == date(2026, 9, 29) and new.original_date == date(2026, 9, 30) and new.group_id == wed.id
    with pytest.raises(ValueError):
        cal.move_session(db, original, date(2026, 9, 28), "שוב", user)
    # התנגשות: אי אפשר להעביר לתאריך שכבר יש בו מפגש לקבוצה
    other = next(s for s in sessions if s.date == date(2026, 9, 23))
    with pytest.raises(ValueError):
        cal.move_session(db, other, date(2026, 9, 29), "x", user)


def test_extra_session_conflict(db, user, groups):
    sun, _ = groups
    cal.generate_month(db, 2026, 9, user)
    with pytest.raises(ValueError):
        cal.add_extra_session(db, sun, date(2026, 9, 6), "כפול", user)
    s = cal.add_extra_session(db, sun, date(2026, 9, 8), "השלמה", user)
    assert s.is_extra and s.date.weekday() == 1


def test_cancel_range_skips_held_sessions(db, user, groups):
    from app.models import AttendanceStatus
    from app.services import attendance as att
    from tests.conftest import make_child

    child = make_child(db, "ילד", groups)
    sessions = cal.generate_month(db, 2026, 9, user)
    first = next(s for s in sessions if s.date == date(2026, 9, 2))
    att.bulk_set(db, first, {child.id: AttendanceStatus.PRESENT}, user)
    done = cal.cancel_range(db, date(2026, 9, 1), date(2026, 9, 13), SessionStatus.CANCELLED_HOLIDAY, "חגים", user)
    assert {s.date for s in done} == {date(2026, 9, 6), date(2026, 9, 9), date(2026, 9, 13)}
    assert first.status.counts_as_held
    with pytest.raises(ValueError):
        cal.cancel_range(db, date(2026, 9, 20), date(2026, 9, 10), SessionStatus.CANCELLED_ADMIN, "", user)
