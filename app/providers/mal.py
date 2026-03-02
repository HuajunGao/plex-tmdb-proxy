"""MAL rating provider.

Uses Jikan v4 (https://jikan.moe) by default — no API key required.
If settings.mal_client_id is set, the official MAL API is tried first.

Results are cached in app.cache for 24 hours.
"""

import logging

import httpx

from app import cache
from app.config import settings
from app.providers.base import RatingResult

logger = logging.getLogger(__name__)

_JIKAN_URL = "https://api.jikan.moe/v4/anime/{mal_id}"
_MAL_URL = "https://api.myanimelist.net/v2/anime/{mal_id}?fields=mean,num_scoring_users"
_CACHE_TTL = 86400  # 24 hours


async def fetch_mal_rating(mal_id: int) -> RatingResult | None:
    """Return a RatingResult from MAL for the given MAL ID, with caching."""
    cache_key = f"mal_rating:{mal_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        if cached == "__NOT_FOUND__":
            return None
        return RatingResult(**cached)

    result: RatingResult | None = None

    # Official MAL API if client_id is configured
    if settings.mal_client_id:
        result = await _fetch_official(mal_id)

    # Jikan v4 as default / fallback
    if result is None:
        result = await _fetch_jikan(mal_id)

    if result:
        cache.set(
            cache_key,
            {"score": result.score, "vote_count": result.vote_count,
             "image": result.image, "source": result.source},
            _CACHE_TTL,
        )
    else:
        cache.set(cache_key, "__NOT_FOUND__", _CACHE_TTL)

    return result


async def _fetch_jikan(mal_id: int) -> RatingResult | None:
    url = _JIKAN_URL.format(mal_id=mal_id)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url)
        if r.status_code == 429:
            logger.warning("Jikan rate-limited for mal_id=%d", mal_id)
            return None
        if r.status_code != 200:
            logger.debug("Jikan %d for mal_id=%d", r.status_code, mal_id)
            return None
        data = r.json().get("data") or {}
        score = data.get("score")
        if not score:
            return None
        return RatingResult(
            score=round(float(score), 1),
            vote_count=data.get("scored_by") or 0,
            image="themoviedb://image.rating",
            source="mal",
        )
    except Exception:
        logger.exception("Jikan fetch failed for mal_id=%d", mal_id)
        return None


async def _fetch_official(mal_id: int) -> RatingResult | None:
    url = _MAL_URL.format(mal_id=mal_id)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                url, headers={"X-MAL-CLIENT-ID": settings.mal_client_id}
            )
        if r.status_code != 200:
            logger.debug("MAL API %d for mal_id=%d", r.status_code, mal_id)
            return None
        data = r.json()
        score = data.get("mean")
        if not score:
            return None
        return RatingResult(
            score=round(float(score), 1),
            vote_count=data.get("num_scoring_users") or 0,
            image="themoviedb://image.rating",
            source="mal",
        )
    except Exception:
        logger.exception("MAL official API failed for mal_id=%d", mal_id)
        return None
