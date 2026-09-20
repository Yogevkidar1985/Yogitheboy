"""נתוני הדגמה: משתמשים, קבוצות ראשון/רביעי, ילדים עם הסדרי חיוב שונים, לוח ספטמבר עם חגים.

הרצה: python scripts/seed_demo.py   (מוחק ויוצר מחדש את המסד שבתיקיית data)
משתמשים: sapir / demo1234 (מנהלת), yahli / demo1234 (תפעולית), admin / demo1234
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402
from app.auth import hash_password  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models import (  # noqa: E402
    AttendanceStatus,
    BillingMethod,
    BillingRule,
    Child,
    ChildContact,
    Contact,
    Group,
    Membership,
    ReceiptMode,
    Role,
    SessionStatus,
    User,
)
from app.services import attendance as att_svc  # noqa: E402
from app.services import calendar as cal_svc  # noqa: E402
from app.services import settings as settings_svc  # noqa: E402


def main() -> None:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    admin = User(username="admin", display_name="מנהל מערכת", password_hash=hash_password("demo1234"), role=Role.ADMIN)
    sapir = User(username="sapir", display_name="ספיר", password_hash=hash_password("demo1234"), role=Role.MANAGER)
    yahli = User(username="yahli", display_name="יהלי", password_hash=hash_password("demo1234"), role=Role.OPERATOR)
    db.add_all([admin, sapir, yahli])
    sun = Group(name="קבוצת ראשון", weekday=6, start_time="16:30")
    wed = Group(name="קבוצת רביעי", weekday=2, start_time="17:00")
    db.add_all([sun, wed])
    db.flush()

    kids = [
        # שם, קבוצות, שיטה, מחיר, קבוע, קבלה, קופ"ח, הורה, טלפון, מייל
        ("נועה לוי", [sun], BillingMethod.PER_ATTENDANCE, 150, 0, ReceiptMode.MONTHLY, "", "דנה לוי", "0521111111", "dana@example.com"),
        ("איתי כהן", [sun], BillingMethod.PER_HELD_SESSION, 150, 0, ReceiptMode.MONTHLY, "", "רון כהן", "0522222222", "ron@example.com"),
        ("לביא מזרחי", [wed], BillingMethod.PER_ATTENDANCE, 160, 0, ReceiptMode.PER_SESSION, "מכבי", "מיכל מזרחי", "0523333333", "michal@example.com"),
        ("תמר אברהם", [sun, wed], BillingMethod.FIXED_MONTHLY, 150, 1000, ReceiptMode.MONTHLY, "", "יעל אברהם", "0524444444", "yael@example.com"),
        ("עידו פרץ", [wed], BillingMethod.CUSTOM, 150, 0, ReceiptMode.MONTHLY, "כללית", "שירה פרץ", "0525555555", "shira@example.com"),
        ("מאיה שלום", [wed], BillingMethod.PER_ATTENDANCE, 140, 0, ReceiptMode.MONTHLY, "", "אורי שלום", "0526666666", "uri@example.com"),
    ]
    children = []
    for name, groups, method, price, fixed, rmode, hmo, pname, phone, email in kids:
        c = Child(full_name=name, national_id="", status="active", joined_on=date(2026, 1, 1), receipt_mode=rmode, hmo=hmo, receipt_notes="טיפול בטיפוס – הדרכה פרטנית" if hmo else "")
        db.add(c)
        db.flush()
        ct = Contact(full_name=pname, phone=phone, email=email)
        db.add(ct)
        db.flush()
        db.add(ChildContact(child_id=c.id, contact_id=ct.id, relation="הורה"))
        for g in groups:
            db.add(Membership(child_id=c.id, group_id=g.id, from_date=date(2026, 1, 1)))
        db.add(BillingRule(child_id=c.id, effective_from=date(2026, 1, 1), method=method, price_per_session=price, fixed_monthly_amount=fixed, description="שני מפגשים בשבוע, 1000 ₪ לחודש" if method == BillingMethod.FIXED_MONTHLY else ("הסדר אישי דרך קופת חולים" if method == BillingMethod.CUSTOM else "")))
        children.append(c)
    db.flush()

    # לוח ספטמבר 2026 עם חגים: ראש השנה (13.9), חוה"מ סוכות – רביעי 30.9 מועבר לשלישי 29.9
    cal_svc.generate_month(db, 2026, 9, sapir)
    db.flush()
    by_date = {(s.date, s.group_id): s for s in cal_svc.month_sessions(db, 2026, 9)}
    cal_svc.cancel_session(db, by_date[(date(2026, 9, 13), sun.id)], SessionStatus.CANCELLED_HOLIDAY, "ראש השנה", sapir)
    cal_svc.move_session(db, by_date[(date(2026, 9, 30), wed.id)], date(2026, 9, 29), "חול המועד סוכות", sapir)
    db.flush()

    # נוכחות למפגשים שכבר התקיימו (עד היום)
    today = date.today()
    for s in cal_svc.month_sessions(db, 2026, 9):
        if s.date >= today or not s.status == SessionStatus.PLANNED:
            continue
        expected = att_svc.expected_children(db, s)
        statuses = {c.id: AttendanceStatus.PRESENT for c in expected}
        # היעדרות אחת לדוגמה
        if s.date.day in (6, 9) and expected:
            statuses[expected[0].id] = AttendanceStatus.ABSENT
        # מפגש אחד עם דיווח חסר כדי להדגים את המשימה בדשבורד
        if s.date == max(x.date for x in cal_svc.month_sessions(db, 2026, 9) if x.date < today):
            statuses = {c.id: AttendanceStatus.PRESENT for c in expected[:-1]} if len(expected) > 1 else statuses
        att_svc.bulk_set(db, s, statuses, yahli)
    settings_svc.set_(db, "signature", "ספיר ויהלי")
    db.commit()
    print(f"נוצרו נתוני הדגמה במסד {config.DATABASE_URL}")
    print("משתמשים: admin / sapir / yahli — סיסמה demo1234")


if __name__ == "__main__":
    main()
