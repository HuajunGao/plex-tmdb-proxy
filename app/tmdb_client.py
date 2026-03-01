import logging
from typing import Any

import httpx

from app.config import settings
from app import cache

logger = logging.getLogger(__name__)

_BASE = "https://api.themoviedb.org/3"
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=15.0)
    return _client


def _params(language: str | None = None, **extra: Any) -> dict:
    p: dict[str, Any] = {"api_key": settings.tmdb_api_key}
    if language:
        p["language"] = language
    p.update(extra)
    return p


async def _get(path: str, language: str | None = None, **extra: Any) -> dict | None:
    url = f"{_BASE}{path}"
    try:
        r = await _get_client().get(url, params=_params(language, **extra))
        if r.status_code == 200:
            return r.json()
        if r.status_code == 404:
            return None
        logger.warning("TMDB %s returned %d", path, r.status_code)
        return None
    except Exception:
        logger.exception("TMDB request failed: %s", path)
        return None


# ── Movie ──


async def get_movie(tmdb_id: int) -> dict | None:
    cache_key = f"movie:{tmdb_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached if cached != "__NOT_FOUND__" else None

    lang = settings.tmdb_language
    data = await _get(
        f"/movie/{tmdb_id}",
        language=lang,
        append_to_response="credits,images,external_ids,similar,release_dates",
        include_image_language=f"{lang[:2]},en,null",
    )
    if data is None:
        cache.set(cache_key, "__NOT_FOUND__", settings.cache_ttl_not_found)
        return None

    # If zh title is same as original, try fallback
    if data.get("title") == data.get("original_title"):
        fb = await _get(f"/movie/{tmdb_id}", language=settings.tmdb_fallback_language)
        if fb and fb.get("title") != data.get("title"):
            data["_fallback_title"] = fb["title"]

    cache.set(cache_key, data)
    return data


async def search_movie(title: str, year: int | None = None) -> list[dict]:
    cache_key = f"search_movie:{title}:{year}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    params: dict[str, Any] = {"query": title}
    if year:
        params["year"] = year
    data = await _get("/search/movie", language=settings.tmdb_language, **params)
    results = (data or {}).get("results", [])
    cache.set(cache_key, results, settings.cache_ttl)
    return results


# ── TV Show ──


async def get_tv(tmdb_id: int) -> dict | None:
    cache_key = f"tv:{tmdb_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached if cached != "__NOT_FOUND__" else None

    lang = settings.tmdb_language
    data = await _get(
        f"/tv/{tmdb_id}",
        language=lang,
        append_to_response="credits,images,external_ids,similar,content_ratings",
        include_image_language=f"{lang[:2]},en,null",
    )
    if data is None:
        cache.set(cache_key, "__NOT_FOUND__", settings.cache_ttl_not_found)
        return None
    cache.set(cache_key, data)
    return data


async def get_tv_season(tmdb_id: int, season_number: int) -> dict | None:
    cache_key = f"tv_season:{tmdb_id}:{season_number}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached if cached != "__NOT_FOUND__" else None

    data = await _get(
        f"/tv/{tmdb_id}/season/{season_number}",
        language=settings.tmdb_language,
        append_to_response="credits,images",
    )
    if data is None:
        cache.set(cache_key, "__NOT_FOUND__", settings.cache_ttl_not_found)
        return None
    cache.set(cache_key, data)
    return data


async def get_tv_episode(
    tmdb_id: int, season_number: int, episode_number: int
) -> dict | None:
    cache_key = f"tv_episode:{tmdb_id}:{season_number}:{episode_number}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached if cached != "__NOT_FOUND__" else None

    data = await _get(
        f"/tv/{tmdb_id}/season/{season_number}/episode/{episode_number}",
        language=settings.tmdb_language,
        append_to_response="credits,images",
    )
    if data is None:
        cache.set(cache_key, "__NOT_FOUND__", settings.cache_ttl_not_found)
        return None
    cache.set(cache_key, data)
    return data


async def search_tv(title: str, year: int | None = None) -> list[dict]:
    cache_key = f"search_tv:{title}:{year}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    params: dict[str, Any] = {"query": title}
    if year:
        params["first_air_date_year"] = year
    data = await _get("/search/tv", language=settings.tmdb_language, **params)
    results = (data or {}).get("results", [])
    cache.set(cache_key, results, settings.cache_ttl)
    return results


async def find_by_external_id(
    external_id: str, source: str = "imdb_id"
) -> dict | None:
    cache_key = f"find:{source}:{external_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    data = await _get(
        f"/find/{external_id}",
        language=settings.tmdb_language,
        external_source=source,
    )
    if data:
        cache.set(cache_key, data, settings.cache_ttl)
    return data
