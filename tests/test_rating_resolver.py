"""Tests for anime_list mapping and rating_resolver."""

import pytest
from unittest.mock import AsyncMock, patch

from app.providers.base import RatingResult


# ── anime_list ────────────────────────────────────────────────────────────────

class TestAnimeList:
    def setup_method(self):
        """Reset in-memory maps before each test."""
        import app.anime_list as al
        al._tv_map = {}
        al._movie_map = {}
        al._ready = False

    def _load(self, entries):
        import app.anime_list as al
        al._build_maps(entries)

    def test_tv_lookup(self):
        from app import anime_list
        self._load([
            {"mal_id": 34599, "themoviedb_id": 71847, "type": "TV"},
            {"mal_id": 50739, "themoviedb_id": 209867, "type": "TV"},
        ])
        assert anime_list.get_mal_id(71847, "tv") == 34599
        assert anime_list.get_mal_id(209867, "tv") == 50739

    def test_movie_lookup(self):
        from app import anime_list
        self._load([
            {"mal_id": 572, "themoviedb_id": 37797, "type": "Movie"},
        ])
        assert anime_list.get_mal_id(37797, "movie") == 572
        assert anime_list.get_mal_id(37797, "tv") is None  # wrong type

    def test_ova_maps_to_tv(self):
        from app import anime_list
        self._load([{"mal_id": 9999, "themoviedb_id": 11111, "type": "OVA"}])
        assert anime_list.get_mal_id(11111, "tv") == 9999

    def test_missing_returns_none(self):
        from app import anime_list
        self._load([])
        assert anime_list.get_mal_id(99999, "tv") is None

    def test_entries_without_ids_are_skipped(self):
        from app import anime_list
        self._load([
            {"mal_id": None, "themoviedb_id": 12345, "type": "TV"},
            {"mal_id": 111, "themoviedb_id": None, "type": "TV"},
        ])
        assert anime_list.get_mal_id(12345, "tv") is None


# ── rating_resolver ───────────────────────────────────────────────────────────

TMDB_DATA = {"vote_average": 7.9, "vote_count": 1234}


class TestRatingResolver:
    def setup_method(self):
        import app.anime_list as al
        al._tv_map = {71847: 34599}
        al._movie_map = {37797: 572}
        al._ready = True

    @pytest.mark.asyncio
    async def test_mal_result_when_mapping_and_api_succeed(self):
        from app import rating_resolver
        mal_result = RatingResult(score=8.7, vote_count=592000, image="themoviedb://image.rating", source="mal")
        with patch("app.rating_resolver.fetch_mal_rating", new=AsyncMock(return_value=mal_result)):
            result = await rating_resolver.resolve(71847, "tv", TMDB_DATA)
        assert result.source == "mal"
        assert result.score == 8.7

    @pytest.mark.asyncio
    async def test_falls_back_to_tmdb_when_mal_api_fails(self):
        from app import rating_resolver
        with patch("app.rating_resolver.fetch_mal_rating", new=AsyncMock(return_value=None)):
            result = await rating_resolver.resolve(71847, "tv", TMDB_DATA)
        assert result.source == "tmdb"
        assert result.score == 7.9

    @pytest.mark.asyncio
    async def test_falls_back_to_tmdb_when_no_mapping(self):
        from app import rating_resolver
        result = await rating_resolver.resolve(99999, "tv", TMDB_DATA)
        assert result.source == "tmdb"
        assert result.score == 7.9
        assert result.vote_count == 1234

    @pytest.mark.asyncio
    async def test_apply_to_meta_overwrites_fields(self):
        from app import rating_resolver
        meta = {
            "audienceRating": 7.9,
            "audienceRatingImage": "imdb://image.rating",
            "Rating": [{"value": 7.9}],
            "imdbRatingCount": 1234,
        }
        r = RatingResult(score=8.7, vote_count=592000, image="themoviedb://image.rating", source="mal")
        rating_resolver.apply_to_meta(meta, r, tmdb_score=7.9)
        assert meta["audienceRating"] == 8.7
        assert meta["audienceRatingImage"] == "themoviedb://image.rating"
        assert meta["Rating"][0]["value"] == 8.7
        assert meta["imdbRatingCount"] == 592000

    @pytest.mark.asyncio
    async def test_apply_to_meta_dual_rating_when_mal_and_tmdb_differ(self):
        from app import rating_resolver
        meta = {}
        r = RatingResult(score=8.7, vote_count=592000, image="themoviedb://image.rating", source="mal")
        rating_resolver.apply_to_meta(meta, r, tmdb_score=7.9)
        assert len(meta["Rating"]) == 2
        assert meta["Rating"][0] == {"image": "themoviedb://image.rating", "type": "audience", "value": 8.7}
        assert meta["Rating"][1] == {"image": "imdb://image.rating", "type": "audience", "value": 7.9}

    @pytest.mark.asyncio
    async def test_apply_to_meta_single_rating_when_scores_same(self):
        from app import rating_resolver
        meta = {}
        r = RatingResult(score=8.7, vote_count=100, image="themoviedb://image.rating", source="mal")
        rating_resolver.apply_to_meta(meta, r, tmdb_score=8.7)
        assert len(meta["Rating"]) == 1

    @pytest.mark.asyncio
    async def test_apply_to_meta_single_rating_for_tmdb_source(self):
        from app import rating_resolver
        meta = {}
        r = RatingResult(score=7.9, vote_count=100, image="themoviedb://image.rating", source="tmdb")
        rating_resolver.apply_to_meta(meta, r, tmdb_score=7.9)
        assert len(meta["Rating"]) == 1

    @pytest.mark.asyncio
    async def test_apply_to_meta_noop_on_zero_score(self):
        from app import rating_resolver
        meta = {"audienceRating": 7.9}
        r = RatingResult(score=0.0, vote_count=0, image="themoviedb://image.rating", source="tmdb")
        rating_resolver.apply_to_meta(meta, r, tmdb_score=0.0)
        assert meta["audienceRating"] == 7.9  # unchanged
