"""Resolve the best available audience rating for a TMDB item.

Priority order:
  1. MAL  — via Fribb/anime-lists TMDB→MAL mapping + Jikan/MAL API
  2. TMDB — always available as fallback

Only movie and show (series) level are resolved here.
Seasons and episodes keep their raw TMDB vote scores.
"""

import logging

from app import anime_list
from app.providers.base import RatingResult
from app.providers.mal import fetch_mal_rating

logger = logging.getLogger(__name__)


async def resolve(tmdb_id: int, media_type: str, tmdb_data: dict) -> RatingResult:
    """Return the best available rating.  Always returns a RatingResult.

    media_type: "movie" | "tv"
    """
    mal_id = anime_list.get_mal_id(tmdb_id, media_type)
    if mal_id:
        logger.debug("tmdb_id=%d → mal_id=%d (%s)", tmdb_id, mal_id, media_type)
        mal_result = await fetch_mal_rating(mal_id)
        if mal_result:
            return mal_result

    # TMDB fallback
    score = float(tmdb_data.get("vote_average") or 0.0)
    return RatingResult(
        score=round(score, 1),
        vote_count=int(tmdb_data.get("vote_count") or 0),
        image="themoviedb://image.rating",
        source="tmdb",
    )


def apply_to_meta(meta: dict, result: RatingResult) -> None:
    """Overwrite the rating fields in a metadata dict in-place.

    Always produces a single rating entry using themoviedb://image.rating.
    MAL score is used when available, otherwise falls back to TMDB.
    No-op when score is 0 (avoids showing a 0.0 rating badge).
    """
    if not result.score:
        return
    meta["audienceRating"] = result.score
    meta["audienceRatingImage"] = result.image
    meta["Rating"] = [{"image": result.image, "type": "audience", "value": result.score}]
    if result.vote_count:
        meta["imdbRatingCount"] = result.vote_count
