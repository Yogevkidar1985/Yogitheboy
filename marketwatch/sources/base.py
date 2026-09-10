from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Listing, SearchSpec


class Source(ABC):
    name: str

    @abstractmethod
    def search(self, spec: SearchSpec) -> list[Listing]:
        """Fetch current listings for the spec. Filtering happens later in matcher."""

    def close(self) -> None:  # optional cleanup (browsers, clients)
        pass
