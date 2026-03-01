"""TV provider routes for Plex metadata API."""

import logging

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse

from app.config import settings
from app import tmdb_client, metadata
from app.utils import parse_rating_key
from app.match import handle_match

logger = logging.getLogger(__name__)

router = APIRouter()
ID = settings.provider_identifier


@router.get("/tv")
async def tv_provider_root():
    """Return provider info for TV shows (type=2,3,4)."""
    return {
        "MediaProvider": {
            "identifier": ID,
            "title": settings.provider_title_tv,
            "version": "1.0.0",
            "Types": [
                {"type": 2, "Scheme": [{"scheme": ID}]},
                {"type": 3, "Scheme": [{"scheme": ID}]},
                {"type": 4, "Scheme": [{"scheme": ID}]},
            ],
            "Feature": [
                {"type": "metadata", "key": "/tv/library/metadata"},
                {"type": "match", "key": "/tv/library/metadata/matches"},
            ],
        }
    }


@router.get("/tv/library/metadata/{rating_key}")
async def tv_metadata(
    rating_key: str,
    includeChildren: int = Query(0),
):
    parsed = parse_rating_key(rating_key)
    if not parsed or parsed.media_type != "show":
        return JSONResponse(status_code=404, content={"error": "not found"})

    # Episode: tmdb-show-123-s1e2
    if parsed.season is not None and parsed.episode is not None:
        return await _episode_response(parsed.tmdb_id, parsed.season, parsed.episode)

    # Season: tmdb-show-123-s1
    if parsed.season is not None:
        return await _season_response(parsed.tmdb_id, parsed.season, includeChildren)

    # Show: tmdb-show-123
    return await _show_response(parsed.tmdb_id, includeChildren)


async def _show_response(tmdb_id: int, include_children: int):
    data = await tmdb_client.get_tv(tmdb_id)
    if not data:
        return JSONResponse(status_code=404, content={"error": "not found"})

    meta = metadata.build_show(data, include_children=bool(include_children))
    return {
        "MediaContainer": {
            "offset": 0,
            "totalSize": 1,
            "identifier": ID,
            "size": 1,
            "Metadata": [meta],
        }
    }


async def _season_response(tmdb_id: int, season_number: int, include_children: int):
    show_data = await tmdb_client.get_tv(tmdb_id)
    if not show_data:
        return JSONResponse(status_code=404, content={"error": "not found"})

    season_data = await tmdb_client.get_tv_season(tmdb_id, season_number)
    if not season_data:
        return JSONResponse(status_code=404, content={"error": "not found"})

    meta = metadata.build_season(show_data, season_data, include_children=bool(include_children))
    return {
        "MediaContainer": {
            "offset": 0,
            "totalSize": 1,
            "identifier": ID,
            "size": 1,
            "Metadata": [meta],
        }
    }


async def _episode_response(tmdb_id: int, season_number: int, episode_number: int):
    show_data = await tmdb_client.get_tv(tmdb_id)
    if not show_data:
        return JSONResponse(status_code=404, content={"error": "not found"})

    season_data = await tmdb_client.get_tv_season(tmdb_id, season_number)
    if not season_data:
        return JSONResponse(status_code=404, content={"error": "not found"})

    ep_data = await tmdb_client.get_tv_episode(tmdb_id, season_number, episode_number)
    if not ep_data:
        return JSONResponse(status_code=404, content={"error": "not found"})

    meta = metadata.build_episode(show_data, season_data, ep_data)
    return {
        "MediaContainer": {
            "offset": 0,
            "totalSize": 1,
            "identifier": ID,
            "size": 1,
            "Metadata": [meta],
        }
    }


# ── Children / Grandchildren ──


@router.get("/tv/library/metadata/{rating_key}/children")
async def tv_children(rating_key: str):
    parsed = parse_rating_key(rating_key)
    if not parsed or parsed.media_type != "show":
        return JSONResponse(status_code=404, content={"error": "not found"})

    # Show children → seasons
    if parsed.season is None:
        data = await tmdb_client.get_tv(parsed.tmdb_id)
        if not data:
            return JSONResponse(status_code=404, content={"error": "not found"})
        children = []
        for s in data.get("seasons", []):
            children.append(metadata._build_season_stub(data, s))
        return {
            "MediaContainer": {
                "offset": 0,
                "totalSize": len(children),
                "identifier": ID,
                "size": len(children),
                "Metadata": children,
            }
        }

    # Season children → episodes
    show_data = await tmdb_client.get_tv(parsed.tmdb_id)
    if not show_data:
        return JSONResponse(status_code=404, content={"error": "not found"})
    season_data = await tmdb_client.get_tv_season(parsed.tmdb_id, parsed.season)
    if not season_data:
        return JSONResponse(status_code=404, content={"error": "not found"})

    episodes = []
    for ep in season_data.get("episodes", []):
        episodes.append(metadata.build_episode(show_data, season_data, ep))
    return {
        "MediaContainer": {
            "offset": 0,
            "totalSize": len(episodes),
            "identifier": ID,
            "size": len(episodes),
            "Metadata": episodes,
        }
    }


@router.get("/tv/library/metadata/{rating_key}/images")
async def tv_images(rating_key: str):
    parsed = parse_rating_key(rating_key)
    if not parsed or parsed.media_type != "show":
        return JSONResponse(status_code=404, content={"error": "not found"})

    data = await tmdb_client.get_tv(parsed.tmdb_id)
    if not data:
        return JSONResponse(status_code=404, content={"error": "not found"})

    images = metadata._images_array(data, data.get("name", ""))
    return {
        "MediaContainer": {
            "offset": 0,
            "totalSize": len(images),
            "identifier": ID,
            "size": len(images),
            "Image": images,
        }
    }


@router.post("/tv/library/metadata/matches")
async def tv_match(request: Request):
    body = await request.json()
    return await handle_match(body, media_type="tv")
