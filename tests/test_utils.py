"""Unit tests for the rating key parser."""
import pytest
from app.utils import parse_rating_key, ParsedKey


class TestParseRatingKey:
    def test_movie(self):
        result = parse_rating_key("tmdb-movie-535167")
        assert result is not None
        assert result.media_type == "movie"
        assert result.tmdb_id == 535167
        assert result.season is None
        assert result.episode is None

    def test_show(self):
        result = parse_rating_key("tmdb-show-50878")
        assert result is not None
        assert result.media_type == "show"
        assert result.tmdb_id == 50878
        assert result.season is None
        assert result.episode is None

    def test_season(self):
        result = parse_rating_key("tmdb-show-50878-s3")
        assert result is not None
        assert result.media_type == "show"
        assert result.tmdb_id == 50878
        assert result.season == 3
        assert result.episode is None

    def test_episode(self):
        result = parse_rating_key("tmdb-show-50878-s3e5")
        assert result is not None
        assert result.media_type == "show"
        assert result.tmdb_id == 50878
        assert result.season == 3
        assert result.episode == 5

    def test_invalid_returns_none(self):
        assert parse_rating_key("invalid") is None
        assert parse_rating_key("") is None
        assert parse_rating_key("tmdb-other-123") is None
        assert parse_rating_key("tmdb-movie-abc") is None

    def test_large_id(self):
        result = parse_rating_key("tmdb-movie-9999999")
        assert result is not None
        assert result.tmdb_id == 9999999
