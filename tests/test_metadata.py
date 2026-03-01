"""Unit tests for the metadata builder."""
import pytest
from app.metadata import (
    build_movie,
    build_show,
    build_season,
    build_episode,
    _img,
    _rating_array,
    _people,
    _images_array,
    _guids,
)
from app.config import settings

ID = settings.provider_identifier


# ── Helpers ──────────────────────────────────────────────────────────────────

def _minimal_movie(tmdb_id: int = 535167, title: str = "流浪地球") -> dict:
    return {
        "id": tmdb_id,
        "title": title,
        "original_title": "The Wandering Earth",
        "overview": "近未来，科学家们发现太阳急速衰老膨胀。",
        "release_date": "2019-02-05",
        "runtime": 126,
        "vote_average": 7.9,
        "poster_path": "/tXuQCgx69DxVgeTsU0TkruR3i9O.jpg",
        "backdrop_path": "/wIrqeoJHYtZmneqIufPtcOHMjOg.jpg",
        "genres": [{"id": 878, "name": "科幻"}, {"id": 28, "name": "动作"}],
        "production_companies": [{"id": 1, "name": "China Film Group Corporation"}],
        "production_countries": [{"iso_3166_1": "CN", "name": "China"}],
        "tagline": "流浪地球，带着家园奔向宇宙",
        "credits": {
            "cast": [
                {"name": "吴京", "character": "刘培强", "profile_path": None, "order": 0},
                {"name": "屈楚萧", "character": "刘启", "profile_path": None, "order": 1},
            ],
            "crew": [
                {"name": "郭帆", "job": "Director", "profile_path": None},
                {"name": "龚格尔", "job": "Producer", "profile_path": None},
            ],
        },
        "images": {"logos": [{"file_path": "/owme6S9tJXYynsrI8gVs2lZ86h3.png"}]},
        "external_ids": {"imdb_id": "tt7605074"},
        "similar": {"results": []},
    }


def _minimal_show(tmdb_id: int = 50878, name: str = "甄嬛传") -> dict:
    return {
        "id": tmdb_id,
        "name": name,
        "original_name": "Empresses in the Palace",
        "overview": "满清初年，后宫争斗。",
        "first_air_date": "2011-11-17",
        "episode_run_time": [45],
        "vote_average": 8.1,
        "poster_path": "/iOMoMkDAAS2lJ1p5yCnKhrToWqc.jpg",
        "backdrop_path": "/c41yiFWQcJd1i8HLlyj8rEbeUcV.jpg",
        "genres": [{"id": 18, "name": "剧情"}],
        "production_companies": [{"id": 2, "name": "北京电视艺术中心"}],
        "production_countries": [{"iso_3166_1": "CN", "name": "China"}],
        "networks": [{"id": 10, "name": "安徽卫视"}],
        "tagline": "真爱与权谋的互相拉锯",
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


def _minimal_season(show_id: int = 50878, season_number: int = 1) -> dict:
    return {
        "id": 99999,
        "season_number": season_number,
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
                "season_number": season_number,
                "air_date": "2011-11-17",
                "still_path": None,
                "runtime": 45,
                "vote_average": 8.0,
                "credits": {"cast": [], "crew": []},
                "external_ids": {},
            }
        ],
    }


# ── Helper unit tests ────────────────────────────────────────────────────────

class TestHelpers:
    def test_img_none(self):
        assert _img(None) is None

    def test_img_returns_full_url(self):
        url = _img("/abc.jpg")
        assert url == f"{settings.tmdb_image_base}/abc.jpg"

    def test_rating_array_zero(self):
        assert _rating_array(0) == []
        assert _rating_array(None) == []

    def test_rating_array_value(self):
        result = _rating_array(7.93)
        assert len(result) == 1
        assert result[0]["value"] == 7.9
        assert result[0]["image"] == "themoviedb://image.rating"

    def test_people_cast(self):
        credits = {
            "cast": [
                {"name": "吴京", "character": "刘培强", "profile_path": None},
                {"name": "屈楚萧", "character": "刘启", "profile_path": "/abc.jpg"},
            ],
            "crew": [],
        }
        cast = _people(credits, "cast")
        assert len(cast) == 2
        assert cast[0]["tag"] == "吴京"
        assert cast[0]["role"] == "刘培强"
        assert cast[1]["thumb"] == _img("/abc.jpg")

    def test_people_director(self):
        credits = {
            "cast": [],
            "crew": [{"name": "郭帆", "job": "Director", "profile_path": None}],
        }
        directors = _people(credits, "director")
        assert len(directors) == 1
        assert directors[0]["tag"] == "郭帆"

    def test_images_array_movie(self):
        data = {"poster_path": "/poster.jpg", "backdrop_path": "/back.jpg", "images": {}}
        imgs = _images_array(data, "Test")
        types = [i["type"] for i in imgs]
        assert "coverPoster" in types
        assert "background" in types

    def test_images_array_episode(self):
        data = {"still_path": "/still.jpg", "backdrop_path": None, "images": {}}
        imgs = _images_array(data, "Ep1", is_episode=True)
        assert imgs[0]["type"] == "snapshot"

    def test_guids(self):
        data = {"id": 535167, "external_ids": {"imdb_id": "tt7605074"}}
        guids = _guids(data)
        ids = [g["id"] for g in guids]
        assert "tmdb://535167" in ids
        assert "imdb://tt7605074" in ids


# ── build_movie ──────────────────────────────────────────────────────────────

class TestBuildMovie:
    def test_required_fields(self):
        meta = build_movie(_minimal_movie())
        assert meta["type"] == "movie"
        assert meta["ratingKey"] == "tmdb-movie-535167"
        assert meta["guid"] == f"{ID}://movie/tmdb-movie-535167"
        assert meta["title"] == "流浪地球"
        assert meta["year"] == 2019
        assert meta["originallyAvailableAt"] == "2019-02-05"

    def test_original_title_when_different(self):
        meta = build_movie(_minimal_movie())
        assert meta.get("originalTitle") == "The Wandering Earth"

    def test_no_original_title_when_same(self):
        data = _minimal_movie()
        data["original_title"] = data["title"]  # same as zh title
        meta = build_movie(data)
        assert "originalTitle" not in meta

    def test_summary(self):
        meta = build_movie(_minimal_movie())
        assert "太阳" in meta["summary"]

    def test_genres_in_chinese(self):
        meta = build_movie(_minimal_movie())
        tags = [g["tag"] for g in meta["Genre"]]
        assert "科幻" in tags
        assert "动作" in tags

    def test_images_present(self):
        meta = build_movie(_minimal_movie())
        assert meta["thumb"] is not None
        assert meta["art"] is not None
        assert any(i["type"] == "coverPoster" for i in meta["Image"])
        assert any(i["type"] == "background" for i in meta["Image"])

    def test_cast(self):
        meta = build_movie(_minimal_movie())
        names = [r["tag"] for r in meta["Role"]]
        assert "吴京" in names

    def test_director(self):
        meta = build_movie(_minimal_movie())
        names = [d["tag"] for d in meta["Director"]]
        assert "郭帆" in names

    def test_guids(self):
        meta = build_movie(_minimal_movie())
        ids = [g["id"] for g in meta["Guid"]]
        assert "tmdb://535167" in ids
        assert "imdb://tt7605074" in ids

    def test_duration_ms(self):
        meta = build_movie(_minimal_movie())
        assert meta["duration"] == 126 * 60000

    def test_missing_release_date(self):
        data = _minimal_movie()
        data["release_date"] = ""
        meta = build_movie(data)
        assert meta["year"] is None


# ── build_show ───────────────────────────────────────────────────────────────

class TestBuildShow:
    def test_required_fields(self):
        meta = build_show(_minimal_show())
        assert meta["type"] == "show"
        assert meta["ratingKey"] == "tmdb-show-50878"
        assert meta["title"] == "甄嬛传"
        assert meta["year"] == 2011

    def test_key_includes_children(self):
        meta = build_show(_minimal_show())
        assert "/children" in meta["key"]

    def test_no_children_by_default(self):
        meta = build_show(_minimal_show())
        assert "Children" not in meta

    def test_include_children(self):
        meta = build_show(_minimal_show(), include_children=True)
        assert "Children" in meta
        assert meta["Children"]["size"] == 1
        assert meta["Children"]["Metadata"][0]["type"] == "season"

    def test_network(self):
        meta = build_show(_minimal_show())
        names = [n["tag"] for n in meta["Network"]]
        assert "安徽卫视" in names


# ── build_season ─────────────────────────────────────────────────────────────

class TestBuildSeason:
    def test_required_fields(self):
        show = _minimal_show()
        season = _minimal_season()
        meta = build_season(show, season)
        assert meta["type"] == "season"
        assert meta["index"] == 1
        assert meta["parentTitle"] == "甄嬛传"
        assert meta["parentType"] == "show"
        assert meta["parentRatingKey"] == "tmdb-show-50878"

    def test_include_children_episodes(self):
        show = _minimal_show()
        season = _minimal_season()
        meta = build_season(show, season, include_children=True)
        assert "Children" in meta
        assert meta["Children"]["size"] == 1
        ep = meta["Children"]["Metadata"][0]
        assert ep["type"] == "episode"
        assert ep["index"] == 1


# ── build_episode ────────────────────────────────────────────────────────────

class TestBuildEpisode:
    def _get_meta(self) -> dict:
        show = _minimal_show()
        season = _minimal_season()
        ep = season["episodes"][0]
        return build_episode(show, season, ep)

    def test_type(self):
        assert self._get_meta()["type"] == "episode"

    def test_indexes(self):
        meta = self._get_meta()
        assert meta["index"] == 1
        assert meta["parentIndex"] == 1

    def test_grandparent_refs(self):
        meta = self._get_meta()
        assert meta["grandparentTitle"] == "甄嬛传"
        assert meta["grandparentType"] == "show"
        assert "tmdb-show-50878" in meta["grandparentRatingKey"]

    def test_parent_refs(self):
        meta = self._get_meta()
        assert meta["parentType"] == "season"
        assert "tmdb-show-50878-s1" in meta["parentRatingKey"]

    def test_snapshot_image(self):
        show = _minimal_show()
        season = _minimal_season()
        season["episodes"][0]["still_path"] = "/still.jpg"
        ep = season["episodes"][0]
        meta = build_episode(show, season, ep)
        assert any(i["type"] == "snapshot" for i in meta["Image"])
