"""Match endpoint logic for Plex metadata provider."""

import logging
import re

from app.config import settings
from app import tmdb_client, metadata

logger = logging.getLogger(__name__)
ID_MOVIE = settings.provider_identifier_movie
ID_TV = settings.provider_identifier_tv


async def handle_match(body: dict, media_type: str = "movie") -> dict:
    """Handle POST /library/metadata/matches for both movie and TV."""
    plex_type = body.get("type", 1)  # 1=movie, 2=show, 3=season, 4=episode
    title = body.get("title", "")
    parent_title = body.get("parentTitle", "")
    grandparent_title = body.get("grandparentTitle", "")
    year = body.get("year")
    guid = body.get("guid", "")
    index = body.get("index")
    parent_index = body.get("parentIndex")
    include_children = body.get("includeChildren", 0)
    manual = body.get("manual", 0)

    # Try to extract external ID from guid hint
    tmdb_id = _extract_tmdb_id(guid)
    imdb_id = _extract_imdb_id(guid)

    results: list[dict] = []

    if media_type == "movie":
        results = await _match_movie(title, year, tmdb_id, imdb_id, manual)
    else:
        # TV provider: default plex_type to 2 (show) if not specified in body
        if plex_type == 1:
            plex_type = 2
        results = await _match_tv(
            title, parent_title, grandparent_title,
            year, tmdb_id, imdb_id,
            plex_type, index, parent_index,
            include_children, manual,
        )

    return {
        "MediaContainer": {
            "offset": 0,
            "totalSize": len(results),
            "identifier": ID_MOVIE if media_type == "movie" else ID_TV,
            "size": len(results),
            "Metadata": results,
        }
    }


async def _match_movie(
    title: str, year: int | None,
    tmdb_id: int | None, imdb_id: str | None,
    manual: int,
) -> list[dict]:
    # Direct lookup by TMDB ID
    if tmdb_id:
        data = await tmdb_client.get_movie(tmdb_id)
        if data:
            return [metadata.build_movie(data)]

    # Lookup by IMDB ID
    if imdb_id:
        found = await tmdb_client.find_by_external_id(imdb_id, "imdb_id")
        if found:
            movies = found.get("movie_results", [])
            if movies:
                data = await tmdb_client.get_movie(movies[0]["id"])
                if data:
                    return [metadata.build_movie(data)]

    # Search by title
    if title:
        results = await tmdb_client.search_movie(title, year)
        limit = 10 if manual else 1
        out = []
        for r in results[:limit]:
            data = await tmdb_client.get_movie(r["id"])
            if data:
                out.append(metadata.build_movie(data))
        return out

    return []


async def _match_tv(
    title: str, parent_title: str, grandparent_title: str,
    year: int | None, tmdb_id: int | None, imdb_id: str | None,
    plex_type: int, index: int | None, parent_index: int | None,
    include_children: int, manual: int,
) -> list[dict]:
    # For season/episode, the show title is in parentTitle/grandparentTitle
    show_title = title
    if plex_type == 3:
        show_title = parent_title or title
    elif plex_type == 4:
        show_title = grandparent_title or parent_title or title

    show_data = None

    # Direct TMDB ID lookup
    if tmdb_id:
        show_data = await tmdb_client.get_tv(tmdb_id)

    # IMDB ID lookup
    if not show_data and imdb_id:
        found = await tmdb_client.find_by_external_id(imdb_id, "imdb_id")
        if found:
            tv = found.get("tv_results", [])
            if tv:
                show_data = await tmdb_client.get_tv(tv[0]["id"])

    # Search by title
    if not show_data and show_title:
        results = await tmdb_client.search_tv(show_title, year)
        if results:
            if manual:
                out = []
                for r in results[:10]:
                    data = await tmdb_client.get_tv(r["id"])
                    if data:
                        out.append(metadata.build_show(data, include_children=bool(include_children)))
                return out
            show_data = await tmdb_client.get_tv(results[0]["id"])

    if not show_data:
        return []

    # Return appropriate type
    if plex_type == 2:
        return [metadata.build_show(show_data, include_children=bool(include_children))]

    if plex_type == 3 and index is not None:
        season_data = await tmdb_client.get_tv_season(show_data["id"], index)
        if season_data:
            return [metadata.build_season(show_data, season_data, include_children=bool(include_children))]

    if plex_type == 4 and parent_index is not None and index is not None:
        season_data = await tmdb_client.get_tv_season(show_data["id"], parent_index)
        ep_data = await tmdb_client.get_tv_episode(show_data["id"], parent_index, index)
        if season_data and ep_data:
            return [metadata.build_episode(show_data, season_data, ep_data)]

    return [metadata.build_show(show_data, include_children=bool(include_children))]


def _extract_tmdb_id(guid: str) -> int | None:
    m = re.search(r"tmdb://(\d+)", guid)
    return int(m.group(1)) if m else None


def _extract_imdb_id(guid: str) -> str | None:
    m = re.search(r"(tt\d+)", guid)
    return m.group(1) if m else None
