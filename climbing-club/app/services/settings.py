"""הגדרות עסקיות הנשמרות במסד הנתונים (תבניות, כללים, מדיניות)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import Setting

# מדיניות ביטול מפגש לילדים בתשלום חודשי קבוע. "unset" = טרם הוחלט – המערכת תציג אזהרה ולא תניח כלל.
CANCEL_POLICY_UNSET = "unset"
CANCEL_POLICY_NO_CHANGE = "no_change"          # ביטול אינו משנה את התשלום החודשי
CANCEL_POLICY_CREDIT = "credit_per_session"    # זיכוי בגובה מחיר מפגש על כל מפגש שבוטל

DEFAULT_MESSAGE_TEMPLATE = """שלום {parent_name},

מצורף סיכום הפעילות של {child_name} לחודש {month_name}:

מספר מפגשים שהתקיימו: {sessions_held}
מספר מפגשים שבהם {child_name} נכח/ה: {sessions_attended}
מספר היעדרויות: {sessions_absent}
{previous_balance_line}סכום לתשלום: {amount} ₪

נשמח להסדרת התשלום.

תודה, {signature}"""

DEFAULT_RECEIPT_DESCRIPTION_MONTHLY = "חוג טיפוס טיפולי – {child_name} – חודש {month_name} {year}. מפגשים: {session_dates}"
DEFAULT_RECEIPT_DESCRIPTION_SESSION = "חוג טיפוס טיפולי – {child_name} – מפגש בתאריך {session_date}"
DEFAULT_RECEIPT_DESCRIPTION_INTRO = "מפגש היכרות – חוג טיפוס טיפולי – {child_name} – {session_date}"

DEFAULTS: dict[str, str] = {
    "club_name": "חוג טיפוס טיפולי",
    "signature": "ספיר ויהלי",
    "cancel_policy_fixed_monthly": CANCEL_POLICY_UNSET,
    "message_template": DEFAULT_MESSAGE_TEMPLATE,
    "receipt_description_monthly": DEFAULT_RECEIPT_DESCRIPTION_MONTHLY,
    "receipt_description_session": DEFAULT_RECEIPT_DESCRIPTION_SESSION,
    "receipt_description_intro": DEFAULT_RECEIPT_DESCRIPTION_INTRO,
    "receipt_footer": "",
    "default_price_per_session": "150",
    "intro_session_price": "150",
    "block_close_on_missing_attendance": "1",
}

LABELS: dict[str, str] = {
    "club_name": "שם החוג (מופיע בקבלות ובהודעות)",
    "signature": "חתימה בהודעות תשלום",
    "cancel_policy_fixed_monthly": "מדיניות ביטול מפגש לילדים בתשלום חודשי קבוע",
    "message_template": "תבנית הודעת תשלום",
    "receipt_description_monthly": "תיאור קבלה חודשית",
    "receipt_description_session": "תיאור קבלה למפגש בודד",
    "receipt_description_intro": "תיאור קבלה למפגש היכרות",
    "receipt_footer": "הערת שוליים קבועה בקבלות",
    "default_price_per_session": "מחיר ברירת מחדל למפגש (₪)",
    "intro_session_price": "מחיר ברירת מחדל למפגש היכרות (₪)",
    "block_close_on_missing_attendance": "חסימת סגירת חודש כשחסרה נוכחות (1=חסימה, 0=אזהרה בלבד)",
}


def get(db: Session, key: str) -> str:
    row = db.get(Setting, key)
    if row is None:
        return DEFAULTS.get(key, "")
    return row.value


def get_all(db: Session) -> dict[str, str]:
    out = dict(DEFAULTS)
    for row in db.query(Setting).all():
        out[row.key] = row.value
    return out


def set_(db: Session, key: str, value: str) -> None:
    row = db.get(Setting, key)
    if row is None:
        db.add(Setting(key=key, value=value))
    else:
        row.value = value
