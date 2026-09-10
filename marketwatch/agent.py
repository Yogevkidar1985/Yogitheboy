"""The watch loop: fetch -> filter -> dedupe -> notify."""

from __future__ import annotations

import logging
import random
import time

from .config import Config
from .matcher import matches
from .models import Match
from .notifiers import build_notifiers
from .sources import build_sources
from .store import SeenStore

log = logging.getLogger(__name__)


class Agent:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.store = SeenStore(cfg.db_path)
        self.sources = build_sources(cfg)
        self.notifiers = build_notifiers(cfg)

    # ------------------------------------------------------------------ one pass
    def run_once(self) -> list[Match]:
        found: list[Match] = []
        for spec in self.cfg.searches:
            for source_name in spec.sources:
                source = self.sources[source_name]
                try:
                    listings = source.search(spec)
                except Exception as e:  # noqa: BLE001 - one bad source must not kill the loop
                    log.exception("%s failed for %r: %s", source_name, spec.name, e)
                    continue
                for listing in listings:
                    ok, why = matches(listing, spec)
                    seen, prev_price, notified = self.store.get(listing)
                    if not ok:
                        log.debug("skip %s: %s", listing.key, why)
                        self.store.upsert(listing, notified=False)
                        continue
                    dropped = (
                        prev_price is not None
                        and listing.price is not None
                        and listing.price < prev_price
                    )
                    reason = None
                    if dropped:
                        reason = "price_drop"  # cheaper than last time we saw it
                    elif not notified:
                        reason = "new"  # never alerted (first sighting, or filters changed)
                    if reason:
                        m = Match(listing=listing, spec=spec, reason=reason, previous_price=prev_price)
                        found.append(m)
                        self._notify(m)
                    self.store.upsert(listing, notified=True)
        log.info("pass done: %d alert(s), %d listings known", len(found), self.store.count())
        return found

    def _notify(self, match: Match) -> None:
        for n in self.notifiers:
            try:
                n.notify(match)
            except Exception as e:  # noqa: BLE001
                log.exception("notifier %s failed: %s", type(n).__name__, e)

    # ------------------------------------------------------------------ forever
    def run_forever(self) -> None:
        self._broadcast(
            f"👀 MarketWatch פעיל. עוקב אחרי {len(self.cfg.searches)} חיפושים "
            f"כל ~{self.cfg.interval_seconds // 60} דקות."
        )
        try:
            while True:
                started = time.time()
                try:
                    self.run_once()
                except Exception as e:  # noqa: BLE001
                    log.exception("pass crashed: %s", e)
                elapsed = time.time() - started
                sleep_for = max(
                    10.0,
                    self.cfg.interval_seconds - elapsed + random.uniform(0, self.cfg.jitter_seconds),
                )
                log.info("sleeping %.0fs", sleep_for)
                time.sleep(sleep_for)
        except KeyboardInterrupt:
            log.info("stopped by user")
        finally:
            self.close()

    def _broadcast(self, text: str) -> None:
        for n in self.notifiers:
            try:
                n.send_text(text)
            except Exception:  # noqa: BLE001
                pass

    def close(self) -> None:
        for s in self.sources.values():
            s.close()
        self.store.close()
