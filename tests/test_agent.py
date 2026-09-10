"""End-to-end pass with a fake source and fake notifier (no network)."""

from marketwatch.agent import Agent
from marketwatch.config import Config, TelegramConfig
from marketwatch.models import Listing, SearchSpec
from marketwatch.notifiers.base import Notifier
from marketwatch.sources.base import Source


class FakeSource(Source):
    name = "yad2"

    def __init__(self):
        self.items = []

    def search(self, spec):
        return list(self.items)


class FakeNotifier(Notifier):
    def __init__(self):
        self.sent = []

    def notify(self, match):
        self.sent.append(match)


def make_agent(tmp_path):
    cfg = Config(
        searches=[SearchSpec(name="tv", query="tv", max_price=1000, exclude=["שבור"])],
        db_path=str(tmp_path / "db.sqlite"),
        telegram=TelegramConfig(),
        notify_console=False,
    )
    agent = Agent.__new__(Agent)
    agent.cfg = cfg
    from marketwatch.store import SeenStore
    agent.store = SeenStore(cfg.db_path)
    agent.sources = {"yad2": FakeSource()}
    agent.notifiers = [FakeNotifier()]
    return agent


def test_alert_once_then_price_drop(tmp_path):
    agent = make_agent(tmp_path)
    src, note = agent.sources["yad2"], agent.notifiers[0]
    src.items = [
        Listing("yad2", "good1234", "TV 55", 900.0, "u1"),
        Listing("yad2", "pricey12", "TV 65", 2000.0, "u2"),
        Listing("yad2", "broken12", "TV שבור", 100.0, "u3"),
    ]
    agent.run_once()
    assert [m.listing.listing_id for m in note.sent] == ["good1234"]

    agent.run_once()  # same data -> nothing new
    assert len(note.sent) == 1

    src.items[1].price = 800.0  # pricey item drops into range
    src.items[0].price = 700.0  # already-alerted item gets cheaper
    agent.run_once()
    reasons = {m.listing.listing_id: (m.reason, m.previous_price) for m in note.sent[1:]}
    assert reasons == {"pricey12": ("price_drop", 2000.0), "good1234": ("price_drop", 900.0)}


def test_relaxed_filter_alerts_previously_skipped_item(tmp_path):
    agent = make_agent(tmp_path)
    src, note = agent.sources["yad2"], agent.notifiers[0]
    src.items = [Listing("yad2", "pricey12", "TV 65", 1200.0, "u2")]
    agent.run_once()
    assert note.sent == []
    agent.cfg.searches[0].max_price = 1300  # user raised the budget
    agent.run_once()
    assert [(m.listing.listing_id, m.reason) for m in note.sent] == [("pricey12", "new")]
    agent.run_once()
    assert len(note.sent) == 1
    agent.close()
