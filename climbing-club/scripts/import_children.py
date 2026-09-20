"""ייבוא ילדים והורים מקובץ CSV (ייצוא מהאקסל הקיים).

הרצה:
    python scripts/import_children.py children.csv            # בדיקה בלבד – מציג מה ייובא
    python scripts/import_children.py children.csv --commit   # ייבוא בפועל

עמודות (שורת כותרת בעברית, סדר לא משנה; עמודות חסרות מקבלות ברירת מחדל):
    שם הילד*, תעודת זהות, קבוצה (שמות מופרדים ב-;), תאריך הצטרפות (DD/MM/YYYY),
    שם ההורה, טלפון, מייל, שם המשלם, שיטת חיוב (נוכחות | מפגשים | חודשי | אישי),
    מחיר למפגש, סכום חודשי, הסדר, אופן קבלה (חודשית | למפגש), קופת חולים, הערות לקבלה, הערות
קבוצה שאינה קיימת נוצרת (יום פעילות לפי השם: "ראשון"/"רביעי"; אחרת יש להשלים במסך הקבוצות).
ילד קיים (אותו שם + ת.ז.) אינו נוצר שוב – מוצג כ"קיים".
לייצוא מאקסל: שמירה בשם → CSV UTF-8.
"""
from __future__ import annotations

import csv
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal, init_db  # noqa: E402
from app.models import BillingMethod, BillingRule, Child, ChildContact, Contact, Group, Membership, ReceiptMode  # noqa: E402

METHODS = {"נוכחות": BillingMethod.PER_ATTENDANCE, "מפגשים": BillingMethod.PER_HELD_SESSION, "חודשי": BillingMethod.FIXED_MONTHLY, "אישי": BillingMethod.CUSTOM}
WEEKDAYS = {"ראשון": 6, "שני": 0, "שלישי": 1, "רביעי": 2, "חמישי": 3, "שישי": 4}


def _date(s: str) -> date | None:
    s = (s or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def _money(s: str) -> float:
    try:
        return float((s or "0").replace("₪", "").replace(",", "").strip() or 0)
    except ValueError:
        return 0.0


def main(path: str, commit: bool) -> None:
    init_db()
    db = SessionLocal()
    groups = {g.name: g for g in db.query(Group).all()}
    contacts = {(c.full_name, c.phone): c for c in db.query(Contact).all()}
    created = existing = 0
    with open(path, encoding="utf-8-sig", newline="") as f:
        for i, row in enumerate(csv.DictReader(f), start=2):
            row = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
            name = row.get("שם הילד", "")
            if not name:
                print(f"שורה {i}: אין שם ילד – דילוג")
                continue
            nid = row.get("תעודת זהות", "")
            if db.query(Child).filter_by(full_name=name, national_id=nid).first():
                print(f"שורה {i}: {name} – קיים")
                existing += 1
                continue
            joined = _date(row.get("תאריך הצטרפות", "")) or date.today().replace(day=1)
            child = Child(
                full_name=name,
                national_id=nid,
                joined_on=joined,
                receipt_mode=ReceiptMode.PER_SESSION if "מפגש" in row.get("אופן קבלה", "") else ReceiptMode.MONTHLY,
                hmo=row.get("קופת חולים", ""),
                receipt_notes=row.get("הערות לקבלה", ""),
                notes=row.get("הערות", ""),
            )
            db.add(child)
            db.flush()
            for gname in [g.strip() for g in row.get("קבוצה", "").split(";") if g.strip()]:
                g = groups.get(gname)
                if g is None:
                    wd = next((v for k, v in WEEKDAYS.items() if k in gname), 6)
                    g = Group(name=gname, weekday=wd)
                    db.add(g)
                    db.flush()
                    groups[gname] = g
                    print(f"  נוצרה קבוצה חדשה: {gname} (יום {[k for k, v in WEEKDAYS.items() if v == wd][0]})")
                db.add(Membership(child_id=child.id, group_id=g.id, from_date=joined))
            parent, payer = row.get("שם ההורה", ""), row.get("שם המשלם", "")
            phone, email = row.get("טלפון", ""), row.get("מייל", "")
            if parent:
                c = contacts.get((parent, phone)) or Contact(full_name=parent, phone=phone, email=email)
                if c.id is None:
                    db.add(c)
                    db.flush()
                    contacts[(parent, phone)] = c
                db.add(ChildContact(child_id=child.id, contact_id=c.id, relation="הורה", is_message_contact=True, is_billing_contact=not payer or payer == parent))
            if payer and payer != parent:
                c = contacts.get((payer, "")) or Contact(full_name=payer, email=email if not parent else "")
                if c.id is None:
                    db.add(c)
                    db.flush()
                    contacts[(payer, "")] = c
                db.add(ChildContact(child_id=child.id, contact_id=c.id, relation="משלם", is_message_contact=False, is_billing_contact=True))
            method = next((m for k, m in METHODS.items() if k in row.get("שיטת חיוב", "")), BillingMethod.PER_ATTENDANCE)
            db.add(
                BillingRule(
                    child_id=child.id,
                    effective_from=joined.replace(day=1),
                    method=method,
                    price_per_session=_money(row.get("מחיר למפגש", "")),
                    fixed_monthly_amount=_money(row.get("סכום חודשי", "")),
                    description=row.get("הסדר", ""),
                )
            )
            created += 1
            print(f"שורה {i}: {name} – {method.value}, {row.get('קבוצה', '') or 'ללא קבוצה'}, הורה: {parent or '—'}")
    if commit:
        db.commit()
        print(f"\nיובאו {created} ילדים ({existing} קיימים). ")
    else:
        db.rollback()
        print(f"\nבדיקה בלבד: {created} ילדים ייובאו, {existing} קיימים. להרצה בפועל הוסיפו --commit")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1], "--commit" in sys.argv)
