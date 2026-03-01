"""Movie provider routes for Plex metadata API."""

import logging

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from app.config import settings
from app import tmdb_client, metadata
from app.utils import parse_rating_key
from app.match import handle_match

logger = logging.getLogger(__name__)

router = APIRouter()
ID = settings.provider_identifier_movie


@router.get("/movies")
async def movie_provider_root():
    """Return provider info for movies (type=1)."""
    return {
        "MediaProvider": {
            "identifier": ID,
            "title": settings.provider_title_movie,
            "version": "1.0.0",
            "Types": [
                {"type": 1, "Scheme": [{"scheme": ID}]},
            ],
            "Feature": [
                {"type": "metadata", "key": "/library/metadata"},
                {"type": "match", "key": "/library/metadata/matches"},
            ],
        }
    }


@router.post("/movies/library/metadata/matches")
@router.get("/movies/library/metadata/matches")
async def movie_match(request: Request):
    body = await _parse_request(request)
    logger.debug("movie match request: %s", body)
    return await handle_match(body, media_type="movie")


async def _parse_request(request: Request) -> dict:
    """Accept JSON body, form-encoded body, or query string params."""
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            return await request.json()
        except Exception:
            pass
    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        data = dict(form)
    else:
        data = dict(request.query_params)
    # Coerce numeric strings
    for key in ("type", "year", "manual", "includeChildren", "index", "parentIndex"):
        if key in data and data[key] != "":
            try:
                data[key] = int(data[key])
            except (ValueError, TypeError):
                pass
    return data


@router.get("/movies/library/metadata/{rating_key}")
async def movie_metadata(rating_key: str, request: Request):
    parsed = parse_rating_key(rating_key)
    if not parsed or parsed.media_type != "movie":
        return JSONResponse(status_code=404, content={"error": "not found"})

    data = await tmdb_client.get_movie(parsed.tmdb_id)
    if not data:
        return JSONResponse(status_code=404, content={"error": "not found"})

    meta = metadata.build_movie(data)
    return {
        "MediaContainer": {
            "offset": 0,
            "totalSize": 1,
            "identifier": ID,
            "size": 1,
            "Metadata": [meta],
        }
    }


@router.get("/movies/library/metadata/{rating_key}/images")
async def movie_images(rating_key: str):
    parsed = parse_rating_key(rating_key)
    if not parsed or parsed.media_type != "movie":
        return JSONResponse(status_code=404, content={"error": "not found"})

    data = await tmdb_client.get_movie(parsed.tmdb_id)
    if not data:
        return JSONResponse(status_code=404, content={"error": "not found"})

    images = metadata._images_array(data, data.get("title", ""))
    return {
        "MediaContainer": {
            "offset": 0,
            "totalSize": len(images),
            "identifier": ID,
            "size": len(images),
            "Image": images,
        }
    }
