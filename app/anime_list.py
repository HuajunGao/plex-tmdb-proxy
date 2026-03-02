"""Load and cache the Fribb/anime-lists TMDB ID → MAL ID mapping.

Source: https://github.com/Fribb/anime-lists
The full JSON is ~6 MB and updated daily by the community.
We cache a local copy in cache/anime-list.json and refresh it once per day.
"""

import json
import logging
import time
from pathlib import Path

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_URL = (
    "https://raw.githubusercontent.com/Fribb/anime-lists/master/anime-list-full.json"
)
_FILE = Path(settings.cache_dir) / "anime-list.json"
_MAX_AGE = 86400  # 24 hours

# In-memory lookup tables built once from the JSON
_tv_map: dict[int, int] = {}     # tmdb_id → mal_id  (TV, OVA, ONA, …)
_movie_map: dict[int, int] = {}  # tmdb_id → mal_id  (Movie)
_ready = False


# ── Internal helpers ──────────────────────────────────────────────────────────

def _build_maps(entries: list[dict]) -> None:
    global _tv_map, _movie_map, _ready
    tv: dict[int, int] = {}
    movie: dict[int, int] = {}
    for e in entries:
        mal_id = e.get("mal_id")
        tmdb_id = e.get("themoviedb_id")
        if not mal_id or not tmdb_id:
            continue
        # type values: "TV", "Movie", "OVA", "ONA", "Special", "Music"
        media_type = str(e.get("type", "")).lower()
        target = movie if media_type == "movie" else tv
        # Keep the first mapping found per tmdb_id (typically Season 1 / the
        # "root" entry; later seasons share the same themoviedb_id but map to
        # different mal_ids which we don't need for a show-level rating).
        tmdb_id_int = int(tmdb_id)
        if tmdb_id_int not in target:
            target[tmdb_id_int] = int(mal_id)
    _tv_map = tv
    _movie_map = movie
    _ready = True
    logger.info(
        "anime-list loaded: %d TV/OVA + %d movie entries", len(_tv_map), len(_movie_map)
    )


def _load_from_file() -> bool:
    if not _FILE.exists():
        return False
    try:
        _build_maps(json.loads(_FILE.read_text()))
        return True
    except Exception:
        logger.exception("Failed to parse cached anime-list file")
        return False


# ── Public API ────────────────────────────────────────────────────────────────

async def ensure_loaded() -> None:
    """Download or refresh the mapping file if missing or older than 24 h.

    Safe to call at startup (failures are logged but do not raise).
    """
    global _ready

    file_age = (
        time.time() - _FILE.stat().st_mtime if _FILE.exists() else float("inf")
    )
    needs_download = file_age > _MAX_AGE

    if not needs_download:
        if not _ready:
            _load_from_file()
        return

    logger.info("Downloading anime-list from Fribb/anime-lists …")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(_URL)
            r.raise_for_status()
        _FILE.parent.mkdir(parents=True, exist_ok=True)
        _FILE.write_bytes(r.content)
        _build_maps(r.json())
        logger.info("anime-list saved to %s", _FILE)
    except Exception:
        logger.warning(
            "Could not download anime-list; falling back to cached copy", exc_info=True
        )
        if not _ready:
            _load_from_file()


def get_mal_id(tmdb_id: int, media_type: str) -> int | None:
    """Return the MAL ID for a given TMDB ID, or None if not in the mapping.

    media_type: "movie" | "tv"
    """
    if media_type == "movie":
        return _movie_map.get(tmdb_id)
    return _tv_map.get(tmdb_id)
