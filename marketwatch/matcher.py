"""Decide whether a listing satisfies a SearchSpec."""

from __future__ import annotations

import re
import unicodedata

from .models import Listing, SearchSpec

# Hebrew final letters -> regular letters so "סוף" and "סופ" compare equal.
_FINALS = str.maketrans({"ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ"})
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = text.lower().translate(_FINALS)
    text = _PUNCT.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def _contains(haystack: str, needle: str) -> bool:
    return normalize(needle) in haystack


def matches(listing: Listing, spec: SearchSpec) -> tuple[bool, str]:
    """Return (ok, reason). reason explains a rejection for logging."""
    text = normalize(f"{listing.title} {listing.description}")

    if listing.price is None:
        if not spec.allow_no_price:
            return False, "no price"
    else:
        if spec.max_price is not None and listing.price > spec.max_price:
            return False, f"price {listing.price:.0f} > max {spec.max_price:.0f}"
        if spec.min_price is not None and listing.price < spec.min_price:
            return False, f"price {listing.price:.0f} < min {spec.min_price:.0f}"

    for word in spec.must_include:
        if not _contains(text, word):
            return False, f"missing required word '{word}'"

    if spec.any_of and not any(_contains(text, w) for w in spec.any_of):
        return False, f"none of {spec.any_of} present"

    for word in spec.exclude:
        if _contains(text, word):
            return False, f"excluded word '{word}'"

    return True, "ok"
