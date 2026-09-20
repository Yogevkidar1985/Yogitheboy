"""תיעוד שינויים (audit trail)."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy.orm import Session

from .models import AuditLog, User


def snapshot(obj: Any, fields: list[str] | None = None) -> dict:
    """הופך רשומת SQLAlchemy למילון ניתן לשמירה כ-JSON."""
    if obj is None:
        return {}
    out = {}
    cols = fields or [c.key for c in obj.__table__.columns]
    for k in cols:
        v = getattr(obj, k, None)
        if isinstance(v, Enum):
            v = v.value
        elif isinstance(v, (date, datetime)):
            v = v.isoformat()
        elif isinstance(v, Decimal):
            v = float(v)
        out[k] = v
    return out


def log(
    db: Session,
    user: User | None,
    entity: str,
    entity_id: int | None,
    action: str,
    before: dict | None = None,
    after: dict | None = None,
    note: str = "",
) -> None:
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            user_name=user.display_name if user else "מערכת",
            entity=entity,
            entity_id=entity_id,
            action=action,
            before=before,
            after=after,
            note=note,
        )
    )
