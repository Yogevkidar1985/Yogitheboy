from marketwatch.models import Listing
from marketwatch.store import SeenStore


def test_store_roundtrip(tmp_path):
    s = SeenStore(tmp_path / "x.db")
    l = Listing(source="yad2", listing_id="a1b2", title="t", price=100.0, url="u")
    assert s.get(l) == (False, None, False)
    s.upsert(l, notified=True)
    assert s.get(l) == (True, 100.0, True)
    l.price = 80.0
    s.upsert(l, notified=False)
    assert s.get(l) == (True, 80.0, True)
    assert s.conn.execute("SELECT notified FROM seen").fetchone()[0] == 1  # never downgraded
    assert s.count() == 1
