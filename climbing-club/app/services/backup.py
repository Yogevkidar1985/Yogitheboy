"""גיבוי ושחזור של מסד הנתונים (SQLite)."""
from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from .. import config


def _db_path() -> Path | None:
    url = config.DATABASE_URL
    if not url.startswith("sqlite:///"):
        return None
    return Path(url[len("sqlite:///"):])


def create_backup() -> Path:
    src = _db_path()
    if src is None or not src.exists():
        raise RuntimeError("גיבוי נתמך רק במסד SQLite מקומי")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = config.BACKUP_DIR / f"club-{stamp}.db"
    # שימוש ב-backup API כדי לקבל עותק עקבי גם בזמן כתיבה
    with sqlite3.connect(src) as s, sqlite3.connect(dst) as d:
        s.backup(d)
    return dst


def list_backups() -> list[Path]:
    return sorted(config.BACKUP_DIR.glob("club-*.db"), reverse=True)


def restore_backup(name: str) -> Path:
    src = config.BACKUP_DIR / Path(name).name
    if not src.exists() or src.suffix != ".db":
        raise FileNotFoundError("קובץ הגיבוי לא נמצא")
    dst = _db_path()
    if dst is None:
        raise RuntimeError("שחזור נתמך רק במסד SQLite מקומי")
    safety = create_backup()
    with sqlite3.connect(src) as s, sqlite3.connect(dst) as d:
        s.backup(d)
    return safety
