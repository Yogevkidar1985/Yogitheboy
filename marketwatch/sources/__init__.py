from __future__ import annotations

from .base import Source
from .yad2 import Yad2Source


def build_sources(cfg) -> dict[str, Source]:
    """Instantiate every source referenced by at least one search."""
    wanted = {s for spec in cfg.searches for s in spec.sources}
    sources: dict[str, Source] = {}
    if "yad2" in wanted:
        sources["yad2"] = Yad2Source()
    if "facebook" in wanted:
        from .facebook import FacebookSource  # imports playwright lazily

        sources["facebook"] = FacebookSource(cfg.facebook)
    unknown = wanted - set(sources)
    if unknown:
        raise SystemExit(f"Unknown sources in config: {sorted(unknown)} (known: yad2, facebook)")
    return sources
