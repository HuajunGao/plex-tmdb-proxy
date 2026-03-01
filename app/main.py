"""TMDB Chinese Metadata Provider for Plex."""

import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import settings
from app.routes_movie import router as movie_router
from app.routes_tv import router as tv_router
from app import cache

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="TMDB Chinese Plex Provider", version="1.0.0")
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
