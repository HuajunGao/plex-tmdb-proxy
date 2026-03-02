"""Convert TMDB API responses to Plex metadata provider format."""

from app.config import settings

ID_MOVIE = settings.provider_identifier_movie
ID_TV = settings.provider_identifier_tv
IMG = settings.tmdb_image_base


def _img(path: str | None) -> str | None:
    if not path:
        return None
    return f"{IMG}{path}"


def _rating_array(vote: float | None) -> list[dict]:
    if not vote or vote == 0:
        return []
    return [{"image": "imdb://image.rating", "type": "audience", "value": round(vote, 1)}]


def _people(credits: dict | None, role_type: str) -> list[dict]:
    if not credits:
        return []
    items = []
    if role_type == "cast":
        for i, p in enumerate(credits.get("cast", [])[:20]):
            entry: dict = {"tag": p["name"], "order": i + 1}
            if p.get("profile_path"):
                entry["thumb"] = _img(p["profile_path"])
            if p.get("character"):
                entry["role"] = p["character"]
            items.append(entry)
    else:
        for p in credits.get("crew", []):
            if p.get("job", "").lower() == role_type.lower():
                entry = {"tag": p["name"], "role": p.get("job", role_type.title())}
                if p.get("profile_path"):
                    entry["thumb"] = _img(p["profile_path"])
                items.append(entry)
    return items


def _images_array(data: dict, title: str, is_episode: bool = False) -> list[dict]:
    imgs = []
    poster = data.get("poster_path")
    backdrop = data.get("backdrop_path")
    still = data.get("still_path")

    if is_episode and still:
        imgs.append({"type": "snapshot", "url": _img(still), "alt": title})
    elif poster:
        imgs.append({"type": "coverPoster", "url": _img(poster), "alt": title})
    if backdrop:
        imgs.append({"type": "background", "url": _img(backdrop), "alt": title})

    # Extra images from append_to_response
    images_data = data.get("images", {})
    for logo in images_data.get("logos", [])[:1]:
        if logo.get("file_path"):
            imgs.append({"type": "clearLogo", "url": _img(logo["file_path"]), "alt": title})
    return imgs


def _guids(data: dict) -> list[dict]:
    guids = []
    ext = data.get("external_ids", {})
    tmdb_id = data.get("id")
    if tmdb_id:
        guids.append({"id": f"tmdb://{tmdb_id}"})
    imdb_id = ext.get("imdb_id") or data.get("imdb_id")
    if imdb_id:
        guids.append({"id": f"imdb://{imdb_id}"})
    tvdb_id = ext.get("tvdb_id")
    if tvdb_id:
        guids.append({"id": f"tvdb://{tvdb_id}"})
    return guids


def _content_rating(data: dict, media_type: str = "movie") -> str | None:
    if media_type == "movie":
        for entry in data.get("release_dates", {}).get("results", []):
            if entry.get("iso_3166_1") == "US":
                for rd in entry.get("release_dates", []):
                    if rd.get("certification"):
                        return rd["certification"]
    else:
        for entry in data.get("content_ratings", {}).get("results", []):
            if entry.get("iso_3166_1") == "US":
                rating = entry.get("rating")
                if rating:
                    return rating
    return None


def _rating_key(media_type: str, tmdb_id: int, extra: str = "") -> str:
    return f"tmdb-{media_type}-{tmdb_id}{extra}"


# ── Movie ──


def build_movie(data: dict) -> dict:
    tmdb_id = data["id"]
    rk = _rating_key("movie", tmdb_id)
    title = data.get("title", "")
    original_title = data.get("original_title")

    meta: dict = {
        "ratingKey": rk,
        "key": f"/library/metadata/{rk}",
        "guid": f"{ID_MOVIE}://movie/{rk}",
        "type": "movie",
        "title": title,
        "originallyAvailableAt": data.get("release_date", ""),
        "year": int(data["release_date"][:4]) if data.get("release_date") and len(data["release_date"]) >= 4 else None,
        "summary": data.get("overview", ""),
        "duration": (data.get("runtime") or 0) * 60000,
        "thumb": _img(data.get("poster_path")),
        "art": _img(data.get("backdrop_path")),
    }

    if original_title and original_title != title:
        meta["originalTitle"] = original_title
    elif data.get("_fallback_title") and data["_fallback_title"] != title:
        meta["originalTitle"] = data["_fallback_title"]

    if data.get("tagline"):
        meta["tagline"] = data["tagline"]

    studios = data.get("production_companies", [])
    if studios:
        meta["studio"] = studios[0]["name"]

    meta["Image"] = _images_array(data, title)
    meta["Genre"] = [{"tag": g["name"]} for g in data.get("genres", [])]
    meta["Guid"] = _guids(data)
    meta["Rating"] = _rating_array(data.get("vote_average"))
    if data.get("vote_average"):
        meta["audienceRating"] = round(data["vote_average"], 1)
        meta["audienceRatingImage"] = "imdb://image.rating"
    if data.get("vote_count"):
        meta["imdbRatingCount"] = data["vote_count"]
    cr = _content_rating(data, "movie")
    if cr:
        meta["contentRating"] = cr
    if data.get("budget"):
        meta["budget"] = data["budget"]
    if data.get("revenue"):
        meta["revenue"] = data["revenue"]
    meta["Country"] = [{"tag": c["name"]} for c in data.get("production_countries", [])]

    credits = data.get("credits", {})
    meta["Role"] = _people(credits, "cast")
    meta["Director"] = _people(credits, "director")
    meta["Writer"] = _people(credits, "screenplay") + _people(credits, "writer")
    meta["Producer"] = _people(credits, "producer")

    meta["Studio"] = [{"tag": s["name"]} for s in studios]

    col = data.get("belongs_to_collection")
    if col:
        col_rk = f"tmdb-collection-{col['id']}"
        meta["Collection"] = [{
            "tag": col["name"],
            "guid": f"{ID_MOVIE}://collection/{col_rk}",
            "key": f"/library/metadata/{col_rk}",
            "thumb": _img(col.get("poster_path")),
            "art": _img(col.get("backdrop_path")),
        }]

    meta["Similar"] = [
        {"tag": s.get("title", ""), "guid": f"{ID_MOVIE}://movie/{_rating_key('movie', s['id'])}"}
        for s in (data.get("similar", {}).get("results", []))[:5]
    ]

    return meta


# ── TV Show ──


def build_show(data: dict, include_children: bool = False, seasons_data: list | None = None) -> dict:
    tmdb_id = data["id"]
    rk = _rating_key("show", tmdb_id)
    title = data.get("name", "")
    original_title = data.get("original_name")

    meta: dict = {
        "ratingKey": rk,
        "key": f"/library/metadata/{rk}/children",
        "guid": f"{ID_TV}://show/{rk}",
        "type": "show",
        "title": title,
        "originallyAvailableAt": data.get("first_air_date", ""),
        "year": int(data["first_air_date"][:4]) if data.get("first_air_date") and len(data["first_air_date"]) >= 4 else None,
        "summary": data.get("overview", ""),
        "duration": ((data.get("episode_run_time") or [0])[0] if data.get("episode_run_time") else 0) * 60000,
        "thumb": _img(data.get("poster_path")),
        "art": _img(data.get("backdrop_path")),
    }

    if original_title and original_title != title:
        meta["originalTitle"] = original_title
    if data.get("tagline"):
        meta["tagline"] = data["tagline"]

    studios = data.get("production_companies", [])
    if studios:
        meta["studio"] = studios[0]["name"]

    meta["Image"] = _images_array(data, title)
    meta["Genre"] = [{"tag": g["name"]} for g in data.get("genres", [])]
    meta["Guid"] = _guids(data)
    meta["Rating"] = _rating_array(data.get("vote_average"))
    if data.get("vote_average"):
        meta["audienceRating"] = round(data["vote_average"], 1)
        meta["audienceRatingImage"] = "imdb://image.rating"
    if data.get("vote_count"):
        meta["imdbRatingCount"] = data["vote_count"]
    cr = _content_rating(data, "tv")
    if cr:
        meta["contentRating"] = cr
    _prod_countries = data.get("production_countries") or []
    if not _prod_countries:
        _prod_countries = [{"name": c} for c in data.get("origin_country", [])]
    meta["Country"] = [{"tag": c["name"]} for c in _prod_countries]
    meta["Network"] = [{"tag": n["name"]} for n in data.get("networks", [])]

    credits = data.get("credits", {})
    meta["Role"] = _people(credits, "cast")
    meta["Director"] = _people(credits, "director")
    meta["Writer"] = _people(credits, "screenplay") + _people(credits, "writer")
    meta["Producer"] = _people(credits, "producer")
    meta["Studio"] = [{"tag": s["name"]} for s in studios]
    meta["Similar"] = [
        {"tag": s.get("name", ""), "guid": f"{ID_TV}://show/{_rating_key('show', s['id'])}"}
        for s in (data.get("similar", {}).get("results", []))[:5]
    ]

    if include_children:
        children = []
        for s in data.get("seasons", []):
            children.append(_build_season_stub(data, s))
        meta["Children"] = {"size": len(children), "Metadata": children}

    return meta


def _build_season_stub(show_data: dict, season: dict) -> dict:
    show_id = show_data["id"]
    sn = season["season_number"]
    rk = _rating_key("show", show_id, f"-s{sn}")
    show_rk = _rating_key("show", show_id)
    stub: dict = {
        "ratingKey": rk,
        "key": f"/library/metadata/{rk}/children",
        "guid": f"{ID_TV}://season/{rk}",
        "type": "season",
        "title": season.get("name", f"Season {sn}"),
        "index": sn,
        "parentTitle": show_data.get("name", ""),
        "parentType": "show",
        "parentRatingKey": show_rk,
        "parentGuid": f"{ID_TV}://show/{show_rk}",
        "parentKey": f"/library/metadata/{show_rk}",
        "parentThumb": _img(show_data.get("poster_path")),
        "thumb": _img(season.get("poster_path")),
        "originallyAvailableAt": season.get("air_date", ""),
        "year": int(season["air_date"][:4]) if season.get("air_date") and len(season["air_date"]) >= 4 else None,
    }
    if season.get("overview"):
        stub["summary"] = season["overview"]
    return stub


def build_season(show_data: dict, season_data: dict, include_children: bool = False) -> dict:
    show_id = show_data["id"]
    sn = season_data["season_number"]
    rk = _rating_key("show", show_id, f"-s{sn}")
    show_rk = _rating_key("show", show_id)
    title = season_data.get("name", f"Season {sn}")

    meta: dict = {
        "ratingKey": rk,
        "key": f"/library/metadata/{rk}/children",
        "guid": f"{ID_TV}://season/{rk}",
        "type": "season",
        "title": title,
        "index": sn,
        "parentTitle": show_data.get("name", ""),
        "parentType": "show",
        "parentRatingKey": show_rk,
        "parentGuid": f"{ID_TV}://show/{show_rk}",
        "parentKey": f"/library/metadata/{show_rk}",
        "parentThumb": _img(show_data.get("poster_path")),
        "parentArt": _img(show_data.get("backdrop_path")),
        "thumb": _img(season_data.get("poster_path")),
        "originallyAvailableAt": season_data.get("air_date", ""),
        "year": int(season_data["air_date"][:4]) if season_data.get("air_date") and len(season_data["air_date"]) >= 4 else None,
        "summary": season_data.get("overview", ""),
        "Image": _images_array(season_data, title),
    }

    if include_children:
        children = []
        for ep in season_data.get("episodes", []):
            children.append(build_episode(show_data, season_data, ep))
        meta["Children"] = {"size": len(children), "Metadata": children}

    return meta


def build_episode(show_data: dict, season_data: dict, ep_data: dict) -> dict:
    show_id = show_data["id"]
    sn = ep_data.get("season_number", season_data.get("season_number", 0))
    en = ep_data.get("episode_number", 0)
    rk = _rating_key("show", show_id, f"-s{sn}e{en}")
    season_rk = _rating_key("show", show_id, f"-s{sn}")
    show_rk = _rating_key("show", show_id)
    title = ep_data.get("name", f"Episode {en}")

    meta: dict = {
        "ratingKey": rk,
        "key": f"/library/metadata/{rk}",
        "guid": f"{ID_TV}://episode/{rk}",
        "type": "episode",
        "title": title,
        "summary": ep_data.get("overview", ""),
        "index": en,
        "parentIndex": sn,
        "duration": (ep_data.get("runtime") or 0) * 60000,
        "thumb": _img(ep_data.get("still_path")),
        "originallyAvailableAt": ep_data.get("air_date", ""),
        "year": int(ep_data["air_date"][:4]) if ep_data.get("air_date") and len(ep_data["air_date"]) >= 4 else None,
        "grandparentTitle": show_data.get("name", ""),
        "grandparentType": "show",
        "grandparentRatingKey": show_rk,
        "grandparentGuid": f"{ID_TV}://show/{show_rk}",
        "grandparentKey": f"/library/metadata/{show_rk}",
        "grandparentThumb": _img(show_data.get("poster_path")),
        "grandparentArt": _img(show_data.get("backdrop_path")),
        "parentTitle": season_data.get("name", f"Season {sn}"),
        "parentType": "season",
        "parentRatingKey": season_rk,
        "parentGuid": f"{ID_TV}://season/{season_rk}",
        "parentKey": f"/library/metadata/{season_rk}",
        "parentThumb": _img(season_data.get("poster_path")),
        "Image": _images_array(ep_data, title, is_episode=True),
        "Rating": _rating_array(ep_data.get("vote_average")),
    }
    if ep_data.get("vote_average"):
        meta["audienceRating"] = round(ep_data["vote_average"], 1)
        meta["audienceRatingImage"] = "imdb://image.rating"

    # Episode credits.
    # When fetched individually (get_tv_episode), TMDB returns a nested "credits" dict.
    # When bulk-fetched from a season response, each episode only has top-level "crew"
    # and "guest_stars" fields — no "credits" dict.  We normalise both cases here.
    ep_credits = ep_data.get("credits")
    if ep_credits:
        # Individual episode fetch: full credits dict
        effective_cast = ep_credits.get("cast", [])
        effective_crew = ep_credits.get("crew", [])
    else:
        # Bulk from season: use episode's own crew + guest_stars
        effective_crew = ep_data.get("crew", [])
        effective_cast = ep_data.get("guest_stars", [])
        # Fall back to season-level regular cast when no episode-specific cast
        if not effective_cast:
            effective_cast = season_data.get("credits", {}).get("cast", [])

    normalised = {"cast": effective_cast, "crew": effective_crew}
    meta["Role"] = _people(normalised, "cast")
    meta["Director"] = _people(normalised, "director")
    meta["Writer"] = _people(normalised, "screenplay") + _people(normalised, "writer")

    # Guid for episode
    guids = []
    tmdb_ep_id = ep_data.get("id")
    if tmdb_ep_id:
        guids.append({"id": f"tmdb://{tmdb_ep_id}"})
    ext = ep_data.get("external_ids", {})
    if ext.get("imdb_id"):
        guids.append({"id": f"imdb://{ext['imdb_id']}"})
    if ext.get("tvdb_id"):
        guids.append({"id": f"tvdb://{ext['tvdb_id']}"})
    meta["Guid"] = guids

    return meta



