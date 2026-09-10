"""Yad2 (yad2.co.il) source.

Yad2 has no public API. This source tries two strategies, in order:

1. The JSON gateway the site itself calls (``gw.yad2.co.il``).
2. The HTML search page, extracting the embedded Next.js JSON blob
   (``__NEXT_DATA__``) and walking it for listing-shaped objects.

Both are best-effort and may need adjusting when Yad2 changes its site;
all the site-specific knowledge is isolated in this file.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Iterable, Optional
from urllib.parse import urlencode

import httpx

from ..models import Listing, SearchSpec
from .base import Source

log = logging.getLogger(__name__)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
GATEWAY_URL = "https://gw.yad2.co.il/feed-search-legacy/{category}"
PAGE_URL = "https://www.yad2.co.il/{category}/all"
ITEM_URL = "https://www.yad2.co.il/item/{token}"

_PRICE_RE = re.compile(r"[\d][\d,\.]*")


def parse_price(value: Any) -> Optional[float]:
    """'1,200 ₪' -> 1200.0 ; 1200 -> 1200.0 ; 'לא צוין מחיר' -> None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    m = _PRICE_RE.search(str(value))
    if not m:
        return None
    try:
        num = float(m.group(0).replace(",", ""))
    except ValueError:
        return None
    return num if num > 0 else None


class Yad2Source(Source):
    name = "yad2"

    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(
            headers={
                "User-Agent": UA,
                "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
                "Accept": "application/json, text/html;q=0.9,*/*;q=0.8",
            },
            timeout=30,
            follow_redirects=True,
        )

    # ------------------------------------------------------------------ public
    def search(self, spec: SearchSpec) -> list[Listing]:
        category = spec.yad2_category or "products"
        params = {"text": spec.query}
        if spec.min_price is not None or spec.max_price is not None:
            lo = int(spec.min_price or 0)
            hi = int(spec.max_price) if spec.max_price is not None else -1
            params["price"] = f"{lo}-{hi}"

        listings = self._search_gateway(category, params)
        if not listings:
            listings = self._search_page(category, params)
        log.info("yad2: %d listings for %r", len(listings), spec.query)
        return listings

    def close(self) -> None:
        self.client.close()

    # ---------------------------------------------------------------- strategy 1
    def _search_gateway(self, category: str, params: dict) -> list[Listing]:
        url = GATEWAY_URL.format(category=category) + "?" + urlencode(params)
        try:
            r = self.client.get(url)
            if r.status_code != 200:
                log.debug("yad2 gateway %s -> %s", url, r.status_code)
                return []
            data = r.json()
        except (httpx.HTTPError, ValueError) as e:
            log.debug("yad2 gateway failed: %s", e)
            return []
        return self.parse_json(data)

    # ---------------------------------------------------------------- strategy 2
    def _search_page(self, category: str, params: dict) -> list[Listing]:
        url = PAGE_URL.format(category=category) + "?" + urlencode(params)
        try:
            r = self.client.get(url, headers={"Accept": "text/html"})
        except httpx.HTTPError as e:
            log.warning("yad2 page request failed: %s", e)
            return []
        if r.status_code in (403, 429) or "captcha" in r.text.lower()[:5000]:
            log.warning(
                "yad2 blocked the request (status %s). Yad2 uses bot protection; "
                "slow down the interval or run from a residential IP.",
                r.status_code,
            )
            return []
        if r.status_code != 200:
            log.warning("yad2 page %s -> %s", url, r.status_code)
            return []
        return self.parse_html(r.text)

    # ---------------------------------------------------------------- parsing
    @classmethod
    def parse_html(cls, html: str) -> list[Listing]:
        m = re.search(
            r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL
        )
        if not m:
            log.warning("yad2: __NEXT_DATA__ blob not found in page")
            return []
        try:
            data = json.loads(m.group(1))
        except ValueError:
            log.warning("yad2: could not decode __NEXT_DATA__")
            return []
        return cls.parse_json(data)

    @classmethod
    def parse_json(cls, data: Any) -> list[Listing]:
        """Walk any JSON structure and pull out objects that look like listings."""
        out: dict[str, Listing] = {}
        for obj in _walk_dicts(data):
            listing = cls._listing_from_obj(obj)
            if listing and listing.listing_id not in out:
                out[listing.listing_id] = listing
        return list(out.values())

    @staticmethod
    def _listing_from_obj(obj: dict) -> Optional[Listing]:
        token = obj.get("token") or obj.get("link_token") or obj.get("adNumber") or obj.get("id")
        title = (
            obj.get("title")
            or obj.get("row_1")
            or obj.get("subtitle")
            or (obj.get("metaData") or {}).get("title")
        )
        price_raw = obj.get("price")
        if isinstance(price_raw, dict):
            price_raw = price_raw.get("price") or price_raw.get("value")
        if not token or not title or "price" not in obj:
            return None
        if not isinstance(title, str):
            return None
        token = str(token)
        if not re.fullmatch(r"[A-Za-z0-9_-]{4,}", token):
            return None

        loc = obj.get("city") or obj.get("row_2") or ""
        if isinstance(loc, dict):
            loc = loc.get("text") or loc.get("name") or ""
        address = obj.get("address")
        if not loc and isinstance(address, dict):
            city = address.get("city")
            loc = city.get("text", "") if isinstance(city, dict) else (city or "")

        img = obj.get("img_url") or obj.get("image") or obj.get("coverImage") or ""
        if isinstance(img, dict):
            img = img.get("url") or img.get("src") or ""

        desc = obj.get("description") or obj.get("row_3") or ""
        return Listing(
            source="yad2",
            listing_id=token,
            title=title.strip(),
            price=parse_price(price_raw),
            url=ITEM_URL.format(token=token),
            location=str(loc or "").strip(),
            description=str(desc or "").strip(),
            image_url=str(img or ""),
        )


def _walk_dicts(node: Any) -> Iterable[dict]:
    """Yield every dict nested anywhere inside node (depth-first)."""
    stack = [node]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            yield cur
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
