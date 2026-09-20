"""עזרי תצוגה: רינדור תבניות, הודעות flash, פילטרים לעברית."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlencode

from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from . import auth
from .models import (
    AttendanceStatus,
    BillingMethod,
    ChargeStatus,
    ChildStatus,
    MessageStatus,
    ReceiptKind,
    ReceiptMode,
    ReceiptStatus,
    Role,
    SessionStatus,
)
from .services import attendance as att_svc
from .services import billing as billing_svc
from .services import calendar as cal_svc
from .services import payments as pay_svc
from .services import receipts as rcpt_svc

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

NAV = [
    ("dashboard", "/", "דשבורד", "01"),
    ("children", "/children", "ילדים והורים", "02"),
    ("calendar", "/calendar", "לוח מפגשים", "03"),
    ("attendance", "/attendance", "נוכחות", "04"),
    ("billing", "/billing", "חיובים וגבייה", "05"),
    ("payments", "/payments", "תשלומים", "06"),
    ("receipts", "/receipts", "קבלות", "07"),
    ("settings", "/settings", "הגדרות ודוחות", "08"),
]

CHILD_STATUS_LABELS = {ChildStatus.ACTIVE: "פעיל", ChildStatus.PAUSED: "בהפסקה", ChildStatus.LEFT: "סיים פעילות"}
RECEIPT_MODE_LABELS = {ReceiptMode.MONTHLY: "קבלה חודשית מרוכזת", ReceiptMode.PER_SESSION: "קבלה נפרדת לכל מפגש"}
CHARGE_STATUS_LABELS = {ChargeStatus.DRAFT: "טיוטה", ChargeStatus.APPROVED: "אושר", ChargeStatus.CLOSED: "סגור"}
MESSAGE_STATUS_LABELS = {MessageStatus.DRAFT: "טיוטה", MessageStatus.APPROVED: "אושרה", MessageStatus.SENT: "נשלחה"}
ROLE_LABELS = {Role.ADMIN: "מנהל מערכת", Role.MANAGER: "מנהלת", Role.OPERATOR: "משתמשת תפעולית"}


def fmt_date(d) -> str:
    if not d:
        return ""
    if isinstance(d, str):
        try:
            d = date.fromisoformat(d[:10])
        except ValueError:
            return d
    return d.strftime("%d/%m/%Y")


def fmt_datetime(d) -> str:
    if not d:
        return ""
    return d.strftime("%d/%m/%Y %H:%M")


def fmt_money(x) -> str:
    try:
        x = float(x or 0)
    except (TypeError, ValueError):
        return str(x)
    s = f"{x:,.2f}"
    if s.endswith(".00"):
        s = s[:-3]
    return s + " ₪"


def weekday_name(d: date) -> str:
    return cal_svc.WEEKDAY_NAMES[d.weekday()]


def hebrew_date(d: date) -> str:
    return f"יום {weekday_name(d)}, {d.day} ב{cal_svc.MONTH_NAMES[d.month]} {d.year}"


def label(value) -> str:
    """תווית עברית לכל enum במערכת."""
    tables = [
        cal_svc.STATUS_LABELS,
        att_svc.STATUS_LABELS,
        billing_svc.METHOD_LABELS,
        CHILD_STATUS_LABELS,
        RECEIPT_MODE_LABELS,
        CHARGE_STATUS_LABELS,
        MESSAGE_STATUS_LABELS,
        ROLE_LABELS,
        rcpt_svc.KIND_LABELS,
        rcpt_svc.STATUS_LABELS,
    ]
    # התאמה מדויקת לפי סוג ה-enum (ערכים כמו "draft" חוזרים בכמה enums)
    for t in tables:
        for k, v in t.items():
            if k is value:
                return v
    for t in tables:
        if value in t:
            return t[value]
    if isinstance(value, str):
        for t in tables:
            for k, v in t.items():
                if getattr(k, "value", None) == value:
                    return v
        if value in pay_svc.METHOD_LABELS:
            return pay_svc.METHOD_LABELS[value]
    return str(getattr(value, "value", value))


def badge_class(value) -> str:
    v = getattr(value, "value", value)
    return {
        "planned": "badge-gray",
        "held": "badge-green",
        "pending_attendance": "badge-orange",
        "cancelled_holiday": "badge-blue",
        "cancelled_admin": "badge-red",
        "cancelled_other": "badge-red",
        "moved": "badge-purple",
        "present": "badge-green",
        "absent": "badge-red",
        "unreported": "badge-gray",
        "active": "badge-green",
        "paused": "badge-orange",
        "left": "badge-gray",
        "draft": "badge-gray",
        "approved": "badge-blue",
        "closed": "badge-purple",
        "sent": "badge-green",
        "issued": "badge-blue",
        "failed": "badge-red",
        "cancelled": "badge-gray",
    }.get(v, "badge-gray")


templates.env.filters["date"] = fmt_date
templates.env.filters["datetime"] = fmt_datetime
templates.env.filters["money"] = fmt_money
templates.env.filters["label"] = label
templates.env.filters["badge"] = badge_class
templates.env.filters["weekday"] = weekday_name
templates.env.filters["hebdate"] = hebrew_date
templates.env.globals.update(
    NAV=NAV,
    MONTH_NAMES=cal_svc.MONTH_NAMES,
    WEEKDAY_NAMES=cal_svc.WEEKDAY_NAMES,
    SessionStatus=SessionStatus,
    AttendanceStatus=AttendanceStatus,
    BillingMethod=BillingMethod,
    ChildStatus=ChildStatus,
    ReceiptMode=ReceiptMode,
    ReceiptStatus=ReceiptStatus,
    ReceiptKind=ReceiptKind,
    ChargeStatus=ChargeStatus,
    MessageStatus=MessageStatus,
    Role=Role,
    PAYMENT_METHODS=pay_svc.METHOD_LABELS,
    can=auth.can,
    today=date.today,
    urlencode=urlencode,
)


def flash(request: Request, message: str, kind: str = "success") -> None:
    msgs = request.session.get("flash", [])
    msgs.append({"kind": kind, "text": message})
    request.session["flash"] = msgs


def pop_flash(request: Request) -> list[dict]:
    return request.session.pop("flash", [])


def render(request: Request, name: str, user=None, status_code: int = 200, **ctx):
    ctx.setdefault("user", user)
    ctx["flash_messages"] = pop_flash(request)
    ctx["request"] = request
    ctx["now"] = datetime.now()
    return templates.TemplateResponse(request, name, ctx, status_code=status_code)


def redirect(url: str, status_code: int = 303) -> RedirectResponse:
    return RedirectResponse(url, status_code=status_code)


def parse_date(s: str | None) -> date | None:
    if not s:
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def parse_money(s: str | None) -> float | None:
    if s is None or str(s).strip() == "":
        return None
    try:
        return round(float(str(s).replace(",", "").replace("₪", "").strip()), 2)
    except ValueError:
        return None


def ym_from_query(year: int | None, month: int | None) -> tuple[int, int]:
    t = date.today()
    return (year or t.year), (month or t.month)


def prev_next(year: int, month: int) -> tuple[tuple[int, int], tuple[int, int]]:
    prev = (year - 1, 12) if month == 1 else (year, month - 1)
    nxt = (year + 1, 1) if month == 12 else (year, month + 1)
    return prev, nxt
