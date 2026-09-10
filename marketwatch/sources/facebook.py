"""Facebook Marketplace source (via Playwright).

Facebook has no public Marketplace API and requires a logged-in session to
show search results reliably. Run ``python -m marketwatch fb-login`` once on a
machine with a screen to save your session cookies to ``fb_state.json``; the
watcher then reuses that file headlessly.

Caveats you should know before relying on this:
* Automated access is against Facebook's terms of service. Use a spare account
  and a slow polling interval (>= 5 minutes) to reduce the risk of a block.
* Facebook changes its markup often. Selectors live only in this file.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

from ..models import Listing, SearchSpec
from .base import Source

log = logging.getLogger(__name__)

SEARCH_URL = "https://www.facebook.com/marketplace/{city}/search?query={q}{price}&exact=false"
ITEM_RE = re.compile(r"/marketplace/item/(\d+)")
PRICE_RE = re.compile(r"(?:₪|ILS|\$|€)\s*([\d,\.]+)|([\d,\.]+)\s*(?:₪|ILS)")
FREE_WORDS = ("free", "חינם")


def parse_card_text(text: str) -> tuple[Optional[float], str, str]:
    """Split a marketplace card's text into (price, title, location).

    A card's innerText usually looks like::

        ₪1,200
        iPhone 12 128GB
        Tel Aviv, Israel

    Sometimes the first line is "₪1,200₪1,500" (sale + old price) - we take the first.
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    price: Optional[float] = None
    title, location = "", ""
    rest: list[str] = []
    for ln in lines:
        if price is None and not rest:
            m = PRICE_RE.search(ln)
            if m:
                num = m.group(1) or m.group(2)
                try:
                    price = float(num.replace(",", ""))
                except ValueError:
                    price = None
                continue
            if ln.lower() in FREE_WORDS:
                price = 0.0
                continue
        rest.append(ln)
    if rest:
        title = rest[0]
    if len(rest) > 1:
        location = rest[1]
    return price, title, location


class FacebookSource(Source):
    name = "facebook"

    def __init__(self, cfg):
        self.cfg = cfg
        self._pw = None
        self._browser = None
        self._context = None

    # ------------------------------------------------------------ lifecycle
    def _ensure_browser(self):
        if self._context is not None:
            return
        from playwright.sync_api import sync_playwright

        state = Path(self.cfg.state_file)
        if not state.exists():
            raise RuntimeError(
                f"Facebook session file {state} not found. Run: python -m marketwatch fb-login"
            )
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self.cfg.headless)
        self._context = self._browser.new_context(
            storage_state=str(state),
            locale="he-IL",
            viewport={"width": 1280, "height": 900},
        )

    def close(self) -> None:
        for obj in (self._context, self._browser):
            try:
                if obj:
                    obj.close()
            except Exception:  # noqa: BLE001
                pass
        if self._pw:
            self._pw.stop()
        self._context = self._browser = self._pw = None

    # --------------------------------------------------------------- search
    def search(self, spec: SearchSpec) -> list[Listing]:
        self._ensure_browser()
        price = ""
        if spec.min_price is not None:
            price += f"&minPrice={int(spec.min_price)}"
        if spec.max_price is not None:
            price += f"&maxPrice={int(spec.max_price)}"
        url = SEARCH_URL.format(city=self.cfg.city_slug, q=quote_plus(spec.query), price=price)

        page = self._context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(3000)  # let the feed hydrate
            if "login" in page.url:
                log.error("facebook: session expired - run `python -m marketwatch fb-login` again")
                return []
            # scroll a bit so lazy cards render
            for _ in range(2):
                page.mouse.wheel(0, 2500)
                page.wait_for_timeout(1200)
            cards = page.eval_on_selector_all(
                'a[href*="/marketplace/item/"]',
                "els => els.map(e => ({href: e.getAttribute('href'), text: e.innerText, "
                "img: (e.querySelector('img') || {}).src || ''}))",
            )
        except Exception as e:  # noqa: BLE001
            log.warning("facebook: search failed for %r: %s", spec.query, e)
            return []
        finally:
            page.close()

        listings: dict[str, Listing] = {}
        for c in cards:
            m = ITEM_RE.search(c.get("href") or "")
            if not m:
                continue
            item_id = m.group(1)
            price_val, title, location = parse_card_text(c.get("text") or "")
            if not title:
                continue
            listings[item_id] = Listing(
                source="facebook",
                listing_id=item_id,
                title=title,
                price=price_val,
                url=f"https://www.facebook.com/marketplace/item/{item_id}/",
                location=location,
                image_url=c.get("img") or "",
            )
            if len(listings) >= self.cfg.max_results:
                break
        log.info("facebook: %d listings for %r", len(listings), spec.query)
        return list(listings.values())


def interactive_login(state_file: str) -> None:
    """Open a visible browser, let the user log in, then save cookies."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context(locale="he-IL")
        page = context.new_page()
        page.goto("https://www.facebook.com/login")
        print("\n>>> התחבר לפייסבוק בחלון שנפתח. אחרי שאתה רואה את דף הבית, חזור לכאן ולחץ Enter.")
        input()
        context.storage_state(path=state_file)
        browser.close()
    print(f"נשמר: {state_file}")
