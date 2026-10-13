"""The resolver moved to endslate.matching so the command line can use it too."""
from __future__ import annotations

from endslate.matcher import offline_confidence
from endslate.matching import Resolver, match_items

# Kept so older call sites and tests keep working.
_offline = offline_confidence

__all__ = ["Resolver", "match_items", "offline_confidence", "_offline"]
