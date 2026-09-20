"""מודל הנתונים: ילדים, אנשי קשר, קבוצות, מפגשים, נוכחות, חיובים, תשלומים וקבלות."""
from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now() -> datetime:
    return datetime.now()


# ---------------------------------------------------------------- משתמשים והרשאות


class Role(str, enum.Enum):
    ADMIN = "admin"        # מנהל מערכת
    MANAGER = "manager"    # מנהלת החוג
    OPERATOR = "operator"  # משתמשת תפעולית


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(128))
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.OPERATOR)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class AuditLog(Base):
    """היסטוריית שינויים לכל ישות רגישה."""

    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    user_name: Mapped[str] = mapped_column(String(128), default="")
    entity: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String(64))
    before: Mapped[dict | None] = mapped_column(JSON)
    after: Mapped[dict | None] = mapped_column(JSON)
    note: Mapped[str] = mapped_column(Text, default="")


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


# ---------------------------------------------------------------- ילדים ואנשי קשר


class ChildStatus(str, enum.Enum):
    ACTIVE = "active"      # פעיל
    PAUSED = "paused"      # בהפסקה
    LEFT = "left"          # סיים פעילות


class BillingMethod(str, enum.Enum):
    PER_ATTENDANCE = "per_attendance"      # לפי מפגשים שבהם נכח
    PER_HELD_SESSION = "per_held_session"  # לפי מפגשים שהתקיימו, גם אם החסיר
    FIXED_MONTHLY = "fixed_monthly"        # תשלום חודשי קבוע
    CUSTOM = "custom"                      # הסדר אישי (סכום ידני לכל חודש)


class ReceiptMode(str, enum.Enum):
    MONTHLY = "monthly"          # קבלה חודשית מרוכזת
    PER_SESSION = "per_session"  # קבלה נפרדת לכל מפגש


class Child(Base):
    __tablename__ = "children"
    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(128), index=True)
    national_id: Mapped[str] = mapped_column(String(16), default="")
    birth_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[ChildStatus] = mapped_column(Enum(ChildStatus), default=ChildStatus.ACTIVE)
    joined_on: Mapped[date | None] = mapped_column(Date)
    left_on: Mapped[date | None] = mapped_column(Date)
    receipt_mode: Mapped[ReceiptMode] = mapped_column(Enum(ReceiptMode), default=ReceiptMode.MONTHLY)
    hmo: Mapped[str] = mapped_column(String(128), default="")  # קופת חולים / גורם מממן
    receipt_notes: Mapped[str] = mapped_column(Text, default="")  # הערות קבועות לקבלה
    receipt_required_fields: Mapped[str] = mapped_column(String(256), default="")  # שדות חובה בקבלה, מופרדים בפסיק
    notes: Mapped[str] = mapped_column(Text, default="")  # הערות והנחיות מיוחדות
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    contacts: Mapped[list[ChildContact]] = relationship(back_populates="child", cascade="all, delete-orphan")
    memberships: Mapped[list[Membership]] = relationship(back_populates="child", cascade="all, delete-orphan")
    billing_rules: Mapped[list[BillingRule]] = relationship(
        back_populates="child", cascade="all, delete-orphan", order_by="BillingRule.effective_from"
    )
    attendance: Mapped[list[Attendance]] = relationship(back_populates="child", cascade="all, delete-orphan")

    # ---- עזרים
    def current_rule(self, on: date | None = None) -> BillingRule | None:
        on = on or date.today()
        best = None
        for r in self.billing_rules:
            if r.effective_from <= on and (r.effective_to is None or r.effective_to >= on):
                if best is None or r.effective_from >= best.effective_from:
                    best = r
        return best

    def contacts_by_role(self, *, message: bool | None = None, billing: bool | None = None) -> list[Contact]:
        out = []
        for cc in self.contacts:
            if message is not None and cc.is_message_contact != message:
                continue
            if billing is not None and cc.is_billing_contact != billing:
                continue
            out.append(cc.contact)
        return out

    @property
    def billing_contact(self) -> Contact | None:
        lst = self.contacts_by_role(billing=True)
        return lst[0] if lst else (self.contacts[0].contact if self.contacts else None)

    @property
    def message_contact(self) -> Contact | None:
        lst = self.contacts_by_role(message=True)
        return lst[0] if lst else (self.contacts[0].contact if self.contacts else None)

    def siblings(self) -> list[Child]:
        """ילדים אחרים שחולקים איש קשר (הורה/משלם) עם ילד זה – לשיוך תשלום משפחתי."""
        out: dict[int, Child] = {}
        for cc in self.contacts:
            for other in cc.contact.children:
                if other.child_id != self.id:
                    out[other.child_id] = other.child
        return sorted(out.values(), key=lambda c: c.full_name)

    def active_groups(self, on: date | None = None) -> list[Group]:
        on = on or date.today()
        return [m.group for m in self.memberships if m.covers(on)]


class Contact(Base):
    """הורה או משלם. איש קשר אחד יכול להיות מקושר לכמה ילדים (אחים)."""

    __tablename__ = "contacts"
    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(128), index=True)
    phone: Mapped[str] = mapped_column(String(32), default="")  # טלפון לוואטסאפ
    email: Mapped[str] = mapped_column(String(128), default="")
    national_id: Mapped[str] = mapped_column(String(16), default="")
    address: Mapped[str] = mapped_column(String(256), default="")
    notes: Mapped[str] = mapped_column(Text, default="")

    children: Mapped[list[ChildContact]] = relationship(back_populates="contact", cascade="all, delete-orphan")


class ChildContact(Base):
    __tablename__ = "child_contacts"
    id: Mapped[int] = mapped_column(primary_key=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("children.id", ondelete="CASCADE"))
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"))
    relation: Mapped[str] = mapped_column(String(32), default="הורה")  # הורה / משלם / אחר
    is_message_contact: Mapped[bool] = mapped_column(Boolean, default=True)  # מקבל הודעות תשלום
    is_billing_contact: Mapped[bool] = mapped_column(Boolean, default=True)  # שמו מופיע בקבלה

    child: Mapped[Child] = relationship(back_populates="contacts")
    contact: Mapped[Contact] = relationship(back_populates="children")
    __table_args__ = (UniqueConstraint("child_id", "contact_id"),)


class BillingRule(Base):
    """כללי חיוב עם היסטוריה: שינוי תעריף לא משנה חודשים שכבר חושבו."""

    __tablename__ = "billing_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("children.id", ondelete="CASCADE"))
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    method: Mapped[BillingMethod] = mapped_column(Enum(BillingMethod), default=BillingMethod.PER_ATTENDANCE)
    price_per_session: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    fixed_monthly_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    description: Mapped[str] = mapped_column(Text, default="")  # תיאור ההסדר האישי
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    child: Mapped[Child] = relationship(back_populates="billing_rules")


# ---------------------------------------------------------------- קבוצות ומפגשים


class Group(Base):
    __tablename__ = "groups"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    weekday: Mapped[int] = mapped_column(Integer)  # 0=שני ... 6=ראשון (Python weekday)
    start_time: Mapped[str] = mapped_column(String(5), default="16:00")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str] = mapped_column(Text, default="")

    memberships: Mapped[list[Membership]] = relationship(back_populates="group", cascade="all, delete-orphan")
    sessions: Mapped[list[ClubSession]] = relationship(back_populates="group")


class Membership(Base):
    __tablename__ = "memberships"
    id: Mapped[int] = mapped_column(primary_key=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("children.id", ondelete="CASCADE"))
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))
    from_date: Mapped[date | None] = mapped_column(Date)
    to_date: Mapped[date | None] = mapped_column(Date)

    child: Mapped[Child] = relationship(back_populates="memberships")
    group: Mapped[Group] = relationship(back_populates="memberships")

    def covers(self, on: date) -> bool:
        if self.from_date and on < self.from_date:
            return False
        if self.to_date and on > self.to_date:
            return False
        return True


class SessionStatus(str, enum.Enum):
    PLANNED = "planned"                        # מתוכנן
    HELD = "held"                              # התקיים
    PENDING_ATTENDANCE = "pending_attendance"  # התקיים, ממתין להשלמת נוכחות
    CANCELLED_HOLIDAY = "cancelled_holiday"    # בוטל – חג
    CANCELLED_ADMIN = "cancelled_admin"        # בוטל – מנהלת
    CANCELLED_OTHER = "cancelled_other"        # בוטל – סיבה אחרת
    MOVED = "moved"                            # הועבר למועד אחר

    @property
    def is_cancelled(self) -> bool:
        return self in (
            SessionStatus.CANCELLED_HOLIDAY,
            SessionStatus.CANCELLED_ADMIN,
            SessionStatus.CANCELLED_OTHER,
        )

    @property
    def counts_as_held(self) -> bool:
        return self in (SessionStatus.HELD, SessionStatus.PENDING_ATTENDANCE)


class SessionKind(str, enum.Enum):
    REGULAR = "regular"  # מפגש קבוצה
    INTRO = "intro"      # מפגש היכרות


class ClubSession(Base):
    """מפגש בודד בלוח. מפגש שהועבר נשאר ברשומה המקורית עם קישור למפגש החדש."""

    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"))
    kind: Mapped[SessionKind] = mapped_column(Enum(SessionKind), default=SessionKind.REGULAR)
    status: Mapped[SessionStatus] = mapped_column(Enum(SessionStatus), default=SessionStatus.PLANNED)
    start_time: Mapped[str] = mapped_column(String(5), default="")
    is_extra: Mapped[bool] = mapped_column(Boolean, default=False)  # מפגש בתאריך חריג
    original_date: Mapped[date | None] = mapped_column(Date)  # אם נוצר כתוצאה מהעברה
    moved_to_id: Mapped[int | None] = mapped_column(ForeignKey("sessions.id"))
    reason: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(128), default="")
    changed_by: Mapped[str] = mapped_column(String(128), default="")
    changed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    group: Mapped[Group | None] = relationship(back_populates="sessions")
    moved_to: Mapped[ClubSession | None] = relationship(remote_side=[id], foreign_keys=[moved_to_id])
    attendance: Mapped[list[Attendance]] = relationship(back_populates="session", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("date", "group_id", "kind", name="uq_session_date_group"),)


class AttendanceStatus(str, enum.Enum):
    PRESENT = "present"        # נכח
    ABSENT = "absent"          # החסיר
    UNREPORTED = "unreported"  # לא דווח


class ChargeOverride(str, enum.Enum):
    DEFAULT = "default"      # לפי כלל החיוב של הילד
    CHARGE = "charge"        # לחייב בכל מקרה
    NO_CHARGE = "no_charge"  # לא לחייב בכל מקרה


class Attendance(Base):
    __tablename__ = "attendance"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    child_id: Mapped[int] = mapped_column(ForeignKey("children.id", ondelete="CASCADE"))
    status: Mapped[AttendanceStatus] = mapped_column(Enum(AttendanceStatus), default=AttendanceStatus.UNREPORTED)
    charge_override: Mapped[ChargeOverride] = mapped_column(Enum(ChargeOverride), default=ChargeOverride.DEFAULT)
    price_override: Mapped[float | None] = mapped_column(Numeric(10, 2))  # מחיר חריג למפגש זה
    note: Mapped[str] = mapped_column(String(256), default="")
    reported_at: Mapped[datetime | None] = mapped_column(DateTime)
    reported_by: Mapped[str] = mapped_column(String(128), default="")

    session: Mapped[ClubSession] = relationship(back_populates="attendance")
    child: Mapped[Child] = relationship(back_populates="attendance")
    __table_args__ = (UniqueConstraint("session_id", "child_id"),)


# ---------------------------------------------------------------- חיובים


class ChargeStatus(str, enum.Enum):
    DRAFT = "draft"        # חושב, טרם נבדק
    APPROVED = "approved"  # אושר על ידי המנהלת
    CLOSED = "closed"      # החודש נסגר – קפוא


class MonthlyCharge(Base):
    """סיכום החיוב של ילד לחודש. נשמר כתמונת מצב (snapshot) שאינה משתנה אחרי סגירה."""

    __tablename__ = "monthly_charges"
    id: Mapped[int] = mapped_column(primary_key=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("children.id", ondelete="CASCADE"))
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    status: Mapped[ChargeStatus] = mapped_column(Enum(ChargeStatus), default=ChargeStatus.DRAFT)
    method: Mapped[BillingMethod] = mapped_column(Enum(BillingMethod))
    sessions_held: Mapped[int] = mapped_column(Integer, default=0)
    sessions_attended: Mapped[int] = mapped_column(Integer, default=0)
    sessions_absent: Mapped[int] = mapped_column(Integer, default=0)
    sessions_unreported: Mapped[int] = mapped_column(Integer, default=0)
    sessions_cancelled: Mapped[int] = mapped_column(Integer, default=0)
    price_per_session: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    base_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    adjustments_total: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0)  # סכום לחיוב
    custom_amount: Mapped[float | None] = mapped_column(Numeric(10, 2))  # להסדר אישי – מוזן ידנית
    warnings: Mapped[list | None] = mapped_column(JSON, default=list)
    detail: Mapped[dict | None] = mapped_column(JSON, default=dict)  # פירוט מפגשים
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    approved_by: Mapped[str] = mapped_column(String(128), default="")

    child: Mapped[Child] = relationship()
    allocations: Mapped[list[PaymentAllocation]] = relationship(back_populates="charge")
    message: Mapped[PaymentMessage | None] = relationship(back_populates="charge", uselist=False)
    __table_args__ = (UniqueConstraint("child_id", "year", "month"),)

    @property
    def paid(self) -> float:
        return float(sum(float(a.amount) for a in self.allocations))

    @property
    def balance(self) -> float:
        return round(float(self.amount) - self.paid, 2)


class Adjustment(Base):
    """זיכוי (סכום שלילי) או חיוב נוסף (חיובי) לילד לחודש."""

    __tablename__ = "adjustments"
    id: Mapped[int] = mapped_column(primary_key=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("children.id", ondelete="CASCADE"))
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    reason: Mapped[str] = mapped_column(String(256))
    session_id: Mapped[int | None] = mapped_column(ForeignKey("sessions.id", ondelete="SET NULL"))
    created_by: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    child: Mapped[Child] = relationship()


class MessageStatus(str, enum.Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    SENT = "sent"


class PaymentMessage(Base):
    """הודעת תשלום להורה, נוצרת מתוך החיוב החודשי."""

    __tablename__ = "payment_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    charge_id: Mapped[int] = mapped_column(ForeignKey("monthly_charges.id", ondelete="CASCADE"), unique=True)
    recipient_name: Mapped[str] = mapped_column(String(128), default="")
    recipient_phone: Mapped[str] = mapped_column(String(32), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[MessageStatus] = mapped_column(Enum(MessageStatus), default=MessageStatus.DRAFT)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    sent_by: Mapped[str] = mapped_column(String(128), default="")

    charge: Mapped[MonthlyCharge] = relationship(back_populates="message")


# ---------------------------------------------------------------- תשלומים


class PaymentMethod(str, enum.Enum):
    BANK_TRANSFER = "bank_transfer"
    CASH = "cash"
    CREDIT_CARD = "credit_card"
    CHECK = "check"
    BIT = "bit"
    PAYBOX = "paybox"
    OTHER = "other"


class PaymentSource(str, enum.Enum):
    MANUAL = "manual"          # הזנה ידנית
    SCREENSHOT = "screenshot"  # פוענח מצילום מסך ואושר


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    child_id: Mapped[int | None] = mapped_column(ForeignKey("children.id", ondelete="SET NULL"))  # ריק = טרם שויך
    paid_on: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod), default=PaymentMethod.BANK_TRANSFER)
    payer_name: Mapped[str] = mapped_column(String(128), default="")
    reference: Mapped[str] = mapped_column(String(64), default="")  # מספר אסמכתא
    bank_details: Mapped[str] = mapped_column(String(256), default="")  # מוצג רק למורשים
    notes: Mapped[str] = mapped_column(Text, default="")
    attachment_path: Mapped[str] = mapped_column(String(256), default="")
    source: Mapped[PaymentSource] = mapped_column(Enum(PaymentSource), default=PaymentSource.MANUAL)
    verified: Mapped[bool] = mapped_column(Boolean, default=True)  # תשלום מצילום מסך מאומת רק לאחר אישור
    extracted: Mapped[dict | None] = mapped_column(JSON)  # הנתונים כפי שפוענחו מהצילום
    created_by: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    child: Mapped[Child | None] = relationship()
    allocations: Mapped[list[PaymentAllocation]] = relationship(
        back_populates="payment", cascade="all, delete-orphan"
    )
    receipts: Mapped[list[Receipt]] = relationship(back_populates="payment")

    @property
    def allocated(self) -> float:
        return float(sum(float(a.amount) for a in self.allocations))

    @property
    def unallocated(self) -> float:
        return round(float(self.amount) - self.allocated, 2)


class PaymentAllocation(Base):
    """שיוך של תשלום (או חלק ממנו) לחיוב חודשי. תשלום אחד יכול לכסות כמה חודשים או כמה ילדים."""

    __tablename__ = "payment_allocations"
    id: Mapped[int] = mapped_column(primary_key=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id", ondelete="CASCADE"))
    charge_id: Mapped[int] = mapped_column(ForeignKey("monthly_charges.id", ondelete="CASCADE"))
    amount: Mapped[float] = mapped_column(Numeric(10, 2))

    payment: Mapped[Payment] = relationship(back_populates="allocations")
    charge: Mapped[MonthlyCharge] = relationship(back_populates="allocations")


# ---------------------------------------------------------------- קבלות


class ReceiptKind(str, enum.Enum):
    MONTHLY = "monthly"          # קבלה חודשית מרוכזת
    PER_SESSION = "per_session"  # קבלה למפגש בודד
    INTRO = "intro"              # מפגש היכרות


class ReceiptStatus(str, enum.Enum):
    DRAFT = "draft"        # הוכנה, ממתינה לבדיקה
    APPROVED = "approved"  # אושרה להפקה
    ISSUED = "issued"      # הופקה ב-YPAY
    SENT = "sent"          # נשלחה להורה
    FAILED = "failed"      # ההפקה נכשלה
    CANCELLED = "cancelled"


class Receipt(Base):
    __tablename__ = "receipts"
    id: Mapped[int] = mapped_column(primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)  # מונע קבלה כפולה
    kind: Mapped[ReceiptKind] = mapped_column(Enum(ReceiptKind))
    status: Mapped[ReceiptStatus] = mapped_column(Enum(ReceiptStatus), default=ReceiptStatus.DRAFT)
    child_id: Mapped[int | None] = mapped_column(ForeignKey("children.id", ondelete="SET NULL"))
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id", ondelete="CASCADE"))
    session_id: Mapped[int | None] = mapped_column(ForeignKey("sessions.id", ondelete="SET NULL"))
    charge_id: Mapped[int | None] = mapped_column(ForeignKey("monthly_charges.id", ondelete="SET NULL"))
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    payer_name: Mapped[str] = mapped_column(String(128), default="")
    email: Mapped[str] = mapped_column(String(128), default="")
    description: Mapped[str] = mapped_column(Text, default="")  # פירוט המפגשים
    notes: Mapped[str] = mapped_column(Text, default="")        # הערות אישיות
    data: Mapped[dict | None] = mapped_column(JSON, default=dict)  # כל נתוני הקבלה כפי שיישלחו
    missing_fields: Mapped[list | None] = mapped_column(JSON, default=list)
    provider: Mapped[str] = mapped_column(String(32), default="")
    external_id: Mapped[str] = mapped_column(String(128), default="")
    receipt_number: Mapped[str] = mapped_column(String(64), default="")
    pdf_url: Mapped[str] = mapped_column(String(512), default="")
    error: Mapped[str] = mapped_column(Text, default="")
    approved_by: Mapped[str] = mapped_column(String(128), default="")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    child: Mapped[Child | None] = relationship()
    payment: Mapped[Payment] = relationship(back_populates="receipts")
    session: Mapped[ClubSession | None] = relationship()
    charge: Mapped[MonthlyCharge | None] = relationship()


# ---------------------------------------------------------------- מפגשי היכרות


class IntroSession(Base):
    """מסלול נפרד למפגש היכרות חד-פעמי, בלי להכניס את הילד לקבוצה קבועה."""

    __tablename__ = "intro_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("children.id", ondelete="CASCADE"))
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    payment_id: Mapped[int | None] = mapped_column(ForeignKey("payments.id", ondelete="SET NULL"))
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    child: Mapped[Child] = relationship()
    session: Mapped[ClubSession] = relationship()
    payment: Mapped[Payment | None] = relationship()


# ---------------------------------------------------------------- סגירת חודש


class MonthClosure(Base):
    __tablename__ = "month_closures"
    id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)
    closed_by: Mapped[str] = mapped_column(String(128), default="")
    reopened_at: Mapped[datetime | None] = mapped_column(DateTime)
    notes: Mapped[str] = mapped_column(Text, default="")
    __table_args__ = (UniqueConstraint("year", "month"),)

    @property
    def is_closed(self) -> bool:
        return self.closed_at is not None and self.reopened_at is None
