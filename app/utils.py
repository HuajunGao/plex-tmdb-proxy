"""Rating key parsing utilities."""

import re
from dataclasses import dataclass


@dataclass
class ParsedKey:
    media_type: str  # movie, show
    tmdb_id: int
    season: int | None = None
    episode: int | None = None


def parse_rating_key(key: str) -> ParsedKey | None:
    """Parse rating keys like tmdb-movie-123, tmdb-show-456-s1, tmdb-show-456-s1e2."""
    m = re.match(r"tmdb-(movie|show)-(\d+)(?:-s(\d+))?(?:e(\d+))?$", key)
    if not m:
        return None
    return ParsedKey(
        media_type=m.group(1),
        tmdb_id=int(m.group(2)),
        season=int(m.group(3)) if m.group(3) else None,
        episode=int(m.group(4)) if m.group(4) else None,
    )
