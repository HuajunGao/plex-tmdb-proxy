"""TMDB Chinese Metadata Provider for Plex."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.routes_movie import router as movie_router
from app.routes_tv import router as tv_router
from app import cache, anime_list

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Preload anime-list mapping in the background so startup isn't blocked
    asyncio.create_task(anime_list.ensure_loaded())
    yield


app = FastAPI(title="TMDB Chinese Plex Provider", version="1.0.0", lifespan=lifespan)
app.include_router(movie_router)
app.include_router(tv_router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/health/ready")
async def health_ready():
    return {
        "status": "ok",
        "version": "1.0.0",
        "tmdb_api_key_configured": bool(settings.tmdb_api_key),
        "language": settings.tmdb_language,
        "fallback_language": settings.tmdb_fallback_language,
    }


@app.get("/health/live")
async def health_live():
    return {"status": "ok"}


@app.post("/cache/clear")
async def cache_clear():
    cache.clear()
    return {"status": "cleared"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.port)
