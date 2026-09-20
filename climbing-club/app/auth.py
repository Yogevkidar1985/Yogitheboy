"""כניסה מאובטחת, הצפנת סיסמאות והרשאות לפי תפקיד."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .db import get_db
from .models import Role, User

_ITERATIONS = 310_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return "pbkdf2$%d$%s$%s" % (
        _ITERATIONS,
        base64.b64encode(salt).decode(),
        base64.b64encode(digest).decode(),
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt_b64, digest_b64 = stored.split("$")
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
    except (ValueError, TypeError):
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iters))
    return hmac.compare_digest(digest, expected)


# ---- הרשאות: אילו תפקידים רשאים לבצע כל פעולה
PERMISSIONS: dict[str, set[Role]] = {
    "view": {Role.ADMIN, Role.MANAGER, Role.OPERATOR},
    "attendance": {Role.ADMIN, Role.MANAGER, Role.OPERATOR},
    "children.edit": {Role.ADMIN, Role.MANAGER},
    "calendar.edit": {Role.ADMIN, Role.MANAGER},
    "billing": {Role.ADMIN, Role.MANAGER},
    "payments.add": {Role.ADMIN, Role.MANAGER, Role.OPERATOR},
    "payments.bank_details": {Role.ADMIN, Role.MANAGER},
    "receipts.approve": {Role.ADMIN, Role.MANAGER},
    "month.close": {Role.ADMIN, Role.MANAGER},
    "settings": {Role.ADMIN, Role.MANAGER},
    "users": {Role.ADMIN},
    "audit": {Role.ADMIN, Role.MANAGER},
}


def can(user: User | None, permission: str) -> bool:
    if user is None or not user.is_active:
        return False
    return user.role in PERMISSIONS.get(permission, set())


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    uid = request.session.get("user_id")
    if not uid:
        return None
    user = db.get(User, uid)
    if user is None or not user.is_active:
        request.session.clear()
        return None
    return user


class LoginRequired(HTTPException):
    def __init__(self):
        super().__init__(status_code=401, detail="נדרשת כניסה למערכת")


def require_user(user: User | None = Depends(get_current_user)) -> User:
    if user is None:
        raise LoginRequired()
    return user


def require(permission: str):
    """תלות FastAPI הבודקת הרשאה ספציפית."""

    def _dep(user: User = Depends(require_user)) -> User:
        if not can(user, permission):
            raise HTTPException(status_code=403, detail="אין לך הרשאה לבצע פעולה זו")
        return user

    return _dep
