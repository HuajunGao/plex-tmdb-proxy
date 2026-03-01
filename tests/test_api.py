"""Integration tests for the FastAPI application using TestClient.

All TMDB API calls are mocked so these tests run without network access.
"""
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings

client = TestClient(app)
ID = settings.provider_identifier

# ── Sample TMDB payloads ──────────────────────────────────────────────────────

MOVIE_PAYLOAD = {
    "id": 535167,
    "title": "流浪地球",
    "original_title": "The Wandering Earth",
    "overview": "近未来，科学家们发现太阳急速衰老膨胀。",
    "release_date": "2019-02-05",
    "runtime": 126,
    "vote_average": 7.9,
    "poster_path": "/poster.jpg",
    "backdrop_path": "/back.jpg",
    "genres": [{"id": 878, "name": "科幻"}],
    "production_companies": [],
    "production_countries": [],
    "tagline": "",
    "credits": {"cast": [], "crew": []},
    "images": {"logos": []},
    "external_ids": {"imdb_id": "tt7605074"},
    "similar": {"results": []},
}

SHOW_PAYLOAD = {
    "id": 50878,
    "name": "甄嬛传",
    "original_name": "Empresses in the Palace",
    "overview": "满清初年，后宫争斗。",
    "first_air_date": "2011-11-17",
    "episode_run_time": [45],
    "vote_average": 8.1,
    "poster_path": "/poster.jpg",
    "backdrop_path": "/back.jpg",
    "genres": [{"id": 18, "name": "剧情"}],
    "production_companies": [],
    "production_countries": [],
    "networks": [{"id": 10, "name": "安徽卫视"}],
    "tagline": "",
    "credits": {"cast": [], "crew": []},
    "images": {"logos": []},
    "external_ids": {"imdb_id": "tt2210449", "tvdb_id": 245765},
    "similar": {"results": []},
    "seasons": [
        {
            "season_number": 1,
            "name": "第 1 季",
            "air_date": "2011-11-17",
            "episode_count": 76,
            "poster_path": None,
        }
    ],
}

SEASON_PAYLOAD = {
    "id": 99999,
    "season_number": 1,
    "name": "第 1 季",
    "air_date": "2011-11-17",
    "poster_path": None,
    "overview": "",
    "episodes": [
        {
            "id": 111111,
            "name": "第一集",
            "overview": "甄嬛入宫。",
            "episode_number": 1,
            "season_number": 1,
            "air_date": "2011-11-17",
            "still_path": None,
            "runtime": 45,
            "vote_average": 8.0,
            "credits": {"cast": [], "crew": []},
            "external_ids": {},
        }
    ],
}

SEARCH_RESULTS = [
    {
        "id": 535167,
        "title": "流浪地球",
        "original_title": "The Wandering Earth",
        "release_date": "2019-02-05",
        "poster_path": "/poster.jpg",
    }
]

SEARCH_TV_RESULTS = [
    {
        "id": 50878,
        "name": "甄嬛传",
        "original_name": "Empresses in the Palace",
        "first_air_date": "2011-11-17",
        "poster_path": "/poster.jpg",
    }
]


# ── Health ────────────────────────────────────────────────────────────────────


class TestHealth:
    def test_health(self):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok", "version": "1.0.0"}

    def test_health_live(self):
        r = client.get("/health/live")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_health_ready(self):
        r = client.get("/health/ready")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert isinstance(body["tmdb_api_key_configured"], bool)
        assert body["language"] == settings.tmdb_language


# ── Movie provider ────────────────────────────────────────────────────────────


class TestMovieProviderRoot:
    def test_returns_media_provider(self):
        r = client.get("/movies")
        assert r.status_code == 200
        mp = r.json()["MediaProvider"]
        assert mp["identifier"] == ID
        assert mp["Types"][0]["type"] == 1

    def test_features_present(self):
        r = client.get("/movies")
        features = r.json()["MediaProvider"]["Feature"]
        keys = [f["key"] for f in features]
        assert "/movies/library/metadata" in keys
        assert "/movies/library/metadata/matches" in keys


class TestMovieMetadata:
    def test_found(self):
        with patch(
            "app.routes_movie.tmdb_client.get_movie",
            new_callable=AsyncMock,
            return_value=MOVIE_PAYLOAD,
        ):
            r = client.get("/movies/library/metadata/tmdb-movie-535167")
        assert r.status_code == 200
        mc = r.json()["MediaContainer"]
        assert mc["size"] == 1
        meta = mc["Metadata"][0]
        assert meta["ratingKey"] == "tmdb-movie-535167"
        assert meta["title"] == "流浪地球"
        assert meta["year"] == 2019

    def test_not_found_from_tmdb(self):
        with patch(
            "app.routes_movie.tmdb_client.get_movie",
            new_callable=AsyncMock,
            return_value=None,
        ):
            r = client.get("/movies/library/metadata/tmdb-movie-000001")
        assert r.status_code == 404

    def test_bad_rating_key(self):
        r = client.get("/movies/library/metadata/invalid-key")
        assert r.status_code == 404

    def test_wrong_media_type(self):
        """A show key should be rejected by the movie endpoint."""
        r = client.get("/movies/library/metadata/tmdb-show-50878")
        assert r.status_code == 404


class TestMovieImages:
    def test_images_endpoint(self):
        with patch(
            "app.routes_movie.tmdb_client.get_movie",
            new_callable=AsyncMock,
            return_value=MOVIE_PAYLOAD,
        ):
            r = client.get("/movies/library/metadata/tmdb-movie-535167/images")
        assert r.status_code == 200
        mc = r.json()["MediaContainer"]
        types = [img["type"] for img in mc.get("Image", [])]
        assert "coverPoster" in types


class TestMovieMatch:
    def test_title_search_returns_candidates(self):
        with patch(
            "app.match.tmdb_client.search_movie",
            new_callable=AsyncMock,
            return_value=SEARCH_RESULTS,
        ), patch(
            "app.match.tmdb_client.get_movie",
            new_callable=AsyncMock,
            return_value=MOVIE_PAYLOAD,
        ):
            r = client.post(
                "/movies/library/metadata/matches",
                json={"title": "流浪地球", "year": 2019, "manual": 1},
            )
        assert r.status_code == 200
        mc = r.json()["MediaContainer"]
        assert mc["size"] >= 1
        assert mc["Metadata"][0]["title"] == "流浪地球"


# ── TV provider ───────────────────────────────────────────────────────────────


class TestTVProviderRoot:
    def test_returns_media_provider(self):
        r = client.get("/tv")
        assert r.status_code == 200
        mp = r.json()["MediaProvider"]
        assert mp["identifier"] == ID
        # TV supports types 2 (show), 3 (season), 4 (episode)
        type_nums = [t["type"] for t in mp["Types"]]
        assert 2 in type_nums
        assert 3 in type_nums
        assert 4 in type_nums


class TestTVShowMetadata:
    def test_show_found(self):
        with patch(
            "app.routes_tv.tmdb_client.get_tv",
            new_callable=AsyncMock,
            return_value=SHOW_PAYLOAD,
        ):
            r = client.get("/tv/library/metadata/tmdb-show-50878")
        assert r.status_code == 200
        meta = r.json()["MediaContainer"]["Metadata"][0]
        assert meta["type"] == "show"
        assert meta["title"] == "甄嬛传"
        assert meta["year"] == 2011

    def test_show_not_found(self):
        with patch(
            "app.routes_tv.tmdb_client.get_tv",
            new_callable=AsyncMock,
            return_value=None,
        ):
            r = client.get("/tv/library/metadata/tmdb-show-999999")
        assert r.status_code == 404

    def test_bad_key(self):
        r = client.get("/tv/library/metadata/bad-key")
        assert r.status_code == 404


class TestTVSeasonMetadata:
    def test_season_found(self):
        with patch(
            "app.routes_tv.tmdb_client.get_tv",
            new_callable=AsyncMock,
            return_value=SHOW_PAYLOAD,
        ), patch(
            "app.routes_tv.tmdb_client.get_tv_season",
            new_callable=AsyncMock,
            return_value=SEASON_PAYLOAD,
        ):
            r = client.get("/tv/library/metadata/tmdb-show-50878-s1")
        assert r.status_code == 200
        meta = r.json()["MediaContainer"]["Metadata"][0]
        assert meta["type"] == "season"
        assert meta["index"] == 1
        assert meta["parentTitle"] == "甄嬛传"


class TestTVEpisodeMetadata:
    def test_episode_found(self):
        with patch(
            "app.routes_tv.tmdb_client.get_tv",
            new_callable=AsyncMock,
            return_value=SHOW_PAYLOAD,
        ), patch(
            "app.routes_tv.tmdb_client.get_tv_season",
            new_callable=AsyncMock,
            return_value=SEASON_PAYLOAD,
        ):
            r = client.get("/tv/library/metadata/tmdb-show-50878-s1e1")
        assert r.status_code == 200
        meta = r.json()["MediaContainer"]["Metadata"][0]
        assert meta["type"] == "episode"
        assert meta["index"] == 1
        assert meta["parentIndex"] == 1
        assert meta["grandparentTitle"] == "甄嬛传"


class TestTVChildren:
    def test_show_children_returns_seasons(self):
        with patch(
            "app.routes_tv.tmdb_client.get_tv",
            new_callable=AsyncMock,
            return_value=SHOW_PAYLOAD,
        ):
            r = client.get("/tv/library/metadata/tmdb-show-50878/children")
        assert r.status_code == 200
        mc = r.json()["MediaContainer"]
        assert mc["size"] >= 1
        assert mc["Metadata"][0]["type"] == "season"

    def test_season_children_returns_episodes(self):
        with patch(
            "app.routes_tv.tmdb_client.get_tv",
            new_callable=AsyncMock,
            return_value=SHOW_PAYLOAD,
        ), patch(
            "app.routes_tv.tmdb_client.get_tv_season",
            new_callable=AsyncMock,
            return_value=SEASON_PAYLOAD,
        ):
            r = client.get("/tv/library/metadata/tmdb-show-50878-s1/children")
        assert r.status_code == 200
        mc = r.json()["MediaContainer"]
        assert mc["size"] >= 1
        assert mc["Metadata"][0]["type"] == "episode"


class TestTVMatch:
    def test_title_search_returns_candidates(self):
        with patch(
            "app.match.tmdb_client.search_tv",
            new_callable=AsyncMock,
            return_value=SEARCH_TV_RESULTS,
        ), patch(
            "app.match.tmdb_client.get_tv",
            new_callable=AsyncMock,
            return_value=SHOW_PAYLOAD,
        ):
            r = client.post(
                "/tv/library/metadata/matches",
                json={"title": "甄嬛传", "year": 2011, "manual": 1},
            )
        assert r.status_code == 200
        mc = r.json()["MediaContainer"]
        assert mc["size"] >= 1
        assert mc["Metadata"][0]["title"] == "甄嬛传"


# ── Cache ─────────────────────────────────────────────────────────────────────


class TestCache:
    def test_clear_cache(self):
        r = client.post("/cache/clear")
        assert r.status_code == 200
        assert r.json()["status"] == "cleared"
