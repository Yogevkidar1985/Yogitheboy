import os
import sys
from datetime import date
from pathlib import Path

import pytest

os.environ.setdefault("CLUB_DATA_DIR", "/tmp/claude-club-tests")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.db import Base, make_engine  # noqa: E402
from app.models import (  # noqa: E402
    BillingMethod,
    BillingRule,
    Child,
    ChildContact,
    Contact,
    Group,
    Membership,
    ReceiptMode,
    Role,
    User,
)


@pytest.fixture
def db():
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=True, expire_on_commit=False)
    s = Session()
    yield s
    s.close()


@pytest.fixture
def user(db):
    u = User(username="t", display_name="בודקת", password_hash="x", role=Role.MANAGER)
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def groups(db):
    sun = Group(name="ראשון", weekday=6)
    wed = Group(name="רביעי", weekday=2)
    db.add_all([sun, wed])
    db.flush()
    return sun, wed


def make_child(db, name, groups, method=BillingMethod.PER_ATTENDANCE, price=150, fixed=0, receipt_mode=ReceiptMode.MONTHLY, email="p@example.com", hmo=""):
    c = Child(full_name=name, joined_on=date(2026, 1, 1), receipt_mode=receipt_mode, hmo=hmo)
    db.add(c)
    db.flush()
    ct = Contact(full_name=f"הורה של {name}", phone="0501234567", email=email)
    db.add(ct)
    db.flush()
    db.add(ChildContact(child_id=c.id, contact_id=ct.id))
    for g in groups:
        db.add(Membership(child_id=c.id, group_id=g.id, from_date=date(2026, 1, 1)))
    db.add(BillingRule(child_id=c.id, effective_from=date(2026, 1, 1), method=method, price_per_session=price, fixed_monthly_amount=fixed))
    db.flush()
    db.refresh(c)
    return c
