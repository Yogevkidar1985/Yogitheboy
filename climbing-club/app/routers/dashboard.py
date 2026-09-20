from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..auth import require_user
from ..db import get_db
from ..models import ChargeStatus, Child, ChildStatus, MessageStatus, MonthlyCharge, SessionStatus
from ..services import calendar as cal_svc
from ..services import month_close as mc_svc
from ..services import payments as pay_svc
from ..services import receipts as rcpt_svc
from ..services.attendance import missing_reports
from ..web import render

router = APIRouter()


@router.get("/")
def dashboard(request: Request, db: Session = Depends(get_db), user=Depends(require_user)):
    today = date.today()
    y, m = today.year, today.month
    active = db.query(Child).filter(Child.status == ChildStatus.ACTIVE).count()
    sessions = cal_svc.month_sessions(db, y, m)
    held = [s for s in sessions if s.status.counts_as_held]
    charges = db.query(MonthlyCharge).filter_by(year=y, month=m).all()
    to_collect = sum(c.balance for c in charges if c.status != ChargeStatus.DRAFT)
    charged = sum(float(c.amount) for c in charges)
    paid = sum(c.paid for c in charges)
    planned_count = sum(1 for s in sessions if s.status == SessionStatus.PLANNED)
    pending_receipts = rcpt_svc.pending(db)
    stale = cal_svc.past_sessions_needing_action(db)
    missing = [(s, missing_reports(db, s)) for s in stale if s.status == SessionStatus.PENDING_ATTENDANCE]
    missing = [(s, k) for s, k in missing if k]
    planned_past = [s for s in stale if s.status == SessionStatus.PLANNED]
    msgs_pending = [c for c in charges if c.status != ChargeStatus.DRAFT and (c.message is None or c.message.status != MessageStatus.SENT)]
    unassigned = pay_svc.unassigned_payments(db)
    unallocated = pay_svc.unallocated_payments(db)
    upcoming = (
        db.query(cal_svc.ClubSession)
        .filter(cal_svc.ClubSession.date >= today, cal_svc.ClubSession.status == SessionStatus.PLANNED)
        .order_by(cal_svc.ClubSession.date)
        .limit(5)
        .all()
    )
    tasks = []
    if planned_past:
        tasks.append(("עדכון סטטוס למפגשים שעברו", f"{len(planned_past)} מפגשים שתאריכם עבר עדיין 'מתוכנן'", "/attendance", "action"))
    if missing:
        tasks.append(("השלמת נוכחות למפגש האחרון", f"{len(missing)} מפגשים עם דיווח חסר", f"/attendance?session_id={missing[0][0].id}", "action"))
    if not charges and held:
        tasks.append(("חישוב חיובים לחודש", "טרם חושבו חיובים לחודש הנוכחי", f"/billing?year={y}&month={m}", "pending"))
    drafts = [c for c in charges if c.status == ChargeStatus.DRAFT]
    if drafts:
        tasks.append(("בדיקה ואישור חיובים", f"{len(drafts)} חיובים בטיוטה", f"/billing?year={y}&month={m}", "pending"))
    if msgs_pending:
        tasks.append(("אישור הודעות תשלום להורים", f"{len(msgs_pending)} הודעות טרם נשלחו", f"/billing/messages/list?year={y}&month={m}", "pending"))
    if unassigned or unallocated:
        tasks.append(("בדיקת תשלומים שטרם שויכו לילד", f"{len(unassigned)} ללא ילד, {len(unallocated)} עם יתרה לא משויכת", "/payments?filter=unassigned", "pending"))
    if pending_receipts:
        tasks.append(("אישור קבלות לפני הפקה ושליחה", f"{len(pending_receipts)} קבלות ממתינות", "/receipts", "pending"))
    return render(
        request,
        "dashboard.html",
        user,
        active_children=active,
        held=len(held),
        planned=planned_count,
        charged=charged,
        paid=paid,
        msgs_pending=len(msgs_pending),
        to_collect=to_collect,
        pending_receipts=len(pending_receipts),
        tasks=tasks,
        upcoming=upcoming,
        year=y,
        month=m,
    )
