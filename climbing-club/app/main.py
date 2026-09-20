"""נקודת הכניסה של האפליקציה."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from . import config
from .db import SessionLocal, init_db
from .models import User
from .routers import (
    attendance,
    auth,
    billing,
    calendar,
    children,
    dashboard,
    intro,
    month_close,
    payments,
    receipts,
    settings,
)
from .web import flash, redirect, render

@asynccontextmanager
async def _lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="ניהול חוג טיפוס", docs_url=None, redoc_url=None, lifespan=_lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SECRET_KEY,
    max_age=config.SESSION_MAX_AGE,
    same_site="lax",
    https_only=config.COOKIE_SECURE,
)
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

for r in (auth, dashboard, children, calendar, attendance, billing, payments, receipts, intro, month_close, settings):
    app.include_router(r.router)


@app.middleware("http")
async def _security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    return resp


@app.middleware("http")
async def _first_run(request: Request, call_next):
    """אם אין משתמשים – מפנים למסך הקמה ראשונית."""
    path = request.url.path
    if not path.startswith(("/static", "/setup")):
        db = SessionLocal()
        try:
            has_users = db.query(User.id).first() is not None
        finally:
            db.close()
        if not has_users:
            return redirect("/setup")
    return await call_next(request)


@app.exception_handler(StarletteHTTPException)
async def _http_exc(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 401:
        request.session["next"] = str(request.url.path)
        return redirect("/login")
    if exc.status_code == 403:
        return render(request, "error.html", status_code=403, title="אין הרשאה", message=exc.detail)
    if exc.status_code == 404:
        return render(request, "error.html", status_code=404, title="הדף לא נמצא", message="הקישור אינו קיים.")
    return HTMLResponse(f"<h1>{exc.status_code}</h1><p>{exc.detail}</p>", status_code=exc.status_code)
