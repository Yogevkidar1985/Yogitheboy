"""הגדרות סביבה. כל ערך ניתן לדריסה במשתנה סביבה או בקובץ .env."""
from __future__ import annotations

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = Path(os.environ.get("CLUB_DATA_DIR", BASE_DIR / "data")).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR = DATA_DIR / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.environ.get("CLUB_DATABASE_URL", f"sqlite:///{DATA_DIR / 'club.db'}")


def _secret_key() -> str:
    """מפתח חתימה לעוגיות. נוצר פעם אחת ונשמר בתיקיית הנתונים אם לא הוגדר בסביבה."""
    env = os.environ.get("CLUB_SECRET_KEY")
    if env:
        return env
    key_file = DATA_DIR / ".secret_key"
    if key_file.exists():
        return key_file.read_text().strip()
    key = secrets.token_urlsafe(48)
    key_file.write_text(key)
    try:
        key_file.chmod(0o600)
    except OSError:
        pass
    return key


SECRET_KEY = _secret_key()
SESSION_MAX_AGE = int(os.environ.get("CLUB_SESSION_MAX_AGE", 60 * 60 * 12))  # 12 שעות
COOKIE_SECURE = os.environ.get("CLUB_COOKIE_SECURE", "0") == "1"

# ספק קבלות: mock (סימולציה), manual (הפקה ידנית באתר YPAY ורישום המספר), ypay_api (חיבור API)
RECEIPT_PROVIDER = os.environ.get("CLUB_RECEIPT_PROVIDER", "mock")
YPAY_API_BASE_URL = os.environ.get("YPAY_API_BASE_URL", "")
YPAY_API_KEY = os.environ.get("YPAY_API_KEY", "")
YPAY_API_SECRET = os.environ.get("YPAY_API_SECRET", "")
YPAY_SANDBOX = os.environ.get("YPAY_SANDBOX", "1") == "1"

# פענוח צילומי מסך של אישורי תשלום (אופציונלי)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OCR_MODEL = os.environ.get("CLUB_OCR_MODEL", "claude-opus-5")

MAX_UPLOAD_BYTES = int(os.environ.get("CLUB_MAX_UPLOAD_BYTES", 8 * 1024 * 1024))
