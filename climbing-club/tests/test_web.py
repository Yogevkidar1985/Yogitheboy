"""בדיקות אינטגרציה דרך HTTP: הקמה ראשונית, כניסה והרשאות."""
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def client():
    from app import config

    db_path = Path(config.DATABASE_URL.replace("sqlite:///", ""))
    for p in (db_path, db_path.with_name(db_path.name + "-wal"), db_path.with_name(db_path.name + "-shm")):
        p.unlink(missing_ok=True)
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app, follow_redirects=False) as c:
        yield c


def test_first_run_setup_then_login_and_permissions(client):
    assert client.get("/").headers["location"] == "/setup"
    r = client.post("/setup", data={"display_name": "ספיר", "username": "sapir", "password": "secret123", "password2": "secret123"})
    assert r.status_code == 303 and client.get("/").status_code == 200
    r = client.post("/settings/users", data={"username": "yahli", "display_name": "יהלי", "password": "secret123", "role": "operator"})
    assert r.status_code == 303
    client.post("/logout")
    assert client.get("/").status_code == 303  # דורש כניסה
    assert client.post("/login", data={"username": "yahli", "password": "wrong"}).headers["location"] == "/login"
    client.post("/login", data={"username": "yahli", "password": "secret123"})
    assert client.get("/attendance").status_code == 200
    assert client.get("/settings/users").status_code == 403
    assert client.post("/billing/compute", data={"year": 2026, "month": 9}).status_code == 403
