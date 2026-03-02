from dataclasses import dataclass


@dataclass
class RatingResult:
    score: float
    vote_count: int
    image: str    # Plex image key, e.g. "themoviedb://image.rating"
    source: str   # "mal", "tmdb", …
