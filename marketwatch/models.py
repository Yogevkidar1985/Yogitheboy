from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Listing:
    """A single marketplace listing, normalized across sources."""

    source: str  # "yad2" | "facebook"
    listing_id: str  # stable id within the source
    title: str
    price: Optional[float]  # None when the seller did not publish a price
    url: str
    location: str = ""
    description: str = ""
    image_url: str = ""
    currency: str = "ILS"

    @property
    def key(self) -> str:
        return f"{self.source}:{self.listing_id}"

    def price_text(self) -> str:
        if self.price is None:
            return "ללא מחיר"
        return f"₪{self.price:,.0f}"


@dataclass
class SearchSpec:
    """One thing the user is hunting for."""

    name: str
    query: str
    max_price: Optional[float] = None
    min_price: Optional[float] = None
    must_include: list[str] = field(default_factory=list)  # every word must appear
    any_of: list[str] = field(default_factory=list)  # at least one must appear
    exclude: list[str] = field(default_factory=list)  # none may appear
    sources: list[str] = field(default_factory=lambda: ["yad2"])
    location: str = ""  # free text passed to sources that support it
    allow_no_price: bool = False  # alert on listings without a published price
    yad2_category: str = ""  # optional yad2 category slug, e.g. "products"


@dataclass
class Match:
    listing: Listing
    spec: SearchSpec
    reason: str = "new"  # "new" | "price_drop"
    previous_price: Optional[float] = None
