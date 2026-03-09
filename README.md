# TMDB Chinese Metadata Provider for Plex

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A **self-hosted** custom metadata provider that supplies **Chinese (zh-CN) metadata** from [TMDB](https://www.themoviedb.org/) to Plex Media Server — including **MAL (MyAnimeList) ratings** for anime.

Plex's built-in agents return English-only metadata and miss MAL ratings entirely. This provider fixes both.

## Features

- 🇨🇳 Chinese titles, summaries, and genre tags (`zh-CN`) with English fallback
- 🎬 Full support: Movies · TV Shows · Seasons · Episodes
- 🎌 **Anime ratings from MyAnimeList** via [Fribb/anime-lists](https://github.com/Fribb/anime-lists) mapping — no MAL API key required
- ⭐ Automatic rating source: MAL score when available, TMDB vote_average as fallback
- 👥 **Complete cast for multi-season shows** via TMDB `aggregate_credits` (all seasons union, not just latest)
- 🖼️ Posters, backdrops, and clear logos from TMDB
- 💾 SQLite-based disk cache (7-day TTL)
- 🐳 Docker / Docker Compose ready — deploy to any LXC or VM
- 🔄 `sync_ratings.py` script to backfill ratings into the Plex database

## Architecture

```
Plex Media Server
      │  POST /movies/library/metadata/matches  (match)
      │  GET  /movies/library/metadata/{key}    (metadata)
      ▼
FastAPI App (port 5100)
      │
      ├─ SQLite cache        ./cache/cache.db
      ├─ Anime-list mapping  ./cache/anime-list.json   (Fribb/anime-lists, refreshed every 24h)
      │
      ├─ TMDB API            api.themoviedb.org/3
      └─ Jikan API (MAL)     api.jikan.moe/v4          (anime only, no key needed)
```

## Quick Start

### Prerequisites

- Docker + Docker Compose (or Python 3.10+)
- [TMDB API key](https://www.themoviedb.org/settings/api) (free)

### 1. Clone

```bash
git clone https://github.com/<YOUR_USERNAME>/plex-tmdb-proxy.git
cd plex-tmdb-proxy
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env and set TMDB_API_KEY=your_key_here
```

### 3. Run with Docker Compose

```bash
docker compose up -d
curl http://localhost:5100/health
```

### 4. Run locally (uv)

```bash
uv venv .venv
uv pip install -r requirements.txt --python .venv/bin/python
.venv/bin/python -m uvicorn app.main:app --reload --port 5100
```

## Plex Configuration

### Step 1 — Register providers

Go to **Settings → Metadata Agents → Add Provider** and add both URLs:

| URL | Name | Type |
|-----|------|------|
| `http://<HOST>:5100/movies` | TMDB Chinese (Movies) | Movies |
| `http://<HOST>:5100/tv` | TMDB Chinese (TV Shows) | TV Shows |

Replace `<HOST>` with your server's IP if Plex is on a different machine than the provider.

### Step 2 — Create agents

**Movie Agent:**
1. Metadata Agents → **+ Add Agent**
2. Title: `TMDB Chinese + Plex Movie`
3. Primary: `TMDB Chinese (Movies)`
4. Add `Plex Movie` as secondary (fills in cast, ratings, etc.)

**TV Agent:**
1. Metadata Agents → **+ Add Agent**
2. Title: `TMDB Chinese + Plex TV`
3. Primary: `TMDB Chinese (TV Shows)`
4. Add `Plex Series` as secondary

### Step 3 — Assign to libraries

**Edit Library → Advanced → Agent** → select the new agent → Save.

For existing content: select items → `···` → **Refresh Metadata**.

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/movies` | GET | Movie provider root (Plex registers this) |
| `/movies/library/metadata/{key}` | GET | Fetch movie metadata by rating key |
| `/movies/library/metadata/{key}/images` | GET | Image list for a movie |
| `/movies/library/metadata/matches` | POST | Match movie from Plex hints |
| `/tv` | GET | TV provider root |
| `/tv/library/metadata/{key}` | GET | Fetch show / season / episode |
| `/tv/library/metadata/{key}/children` | GET | List seasons (for show) or episodes (for season) |
| `/tv/library/metadata/{key}/images` | GET | Image list for a show |
| `/tv/library/metadata/matches` | POST | Match TV show/season/episode |
| `/health` | GET | Health check |
| `/health/ready` | GET | Detailed status with config info |
| `/cache/clear` | POST | Clear all cached entries |

### Rating key format

```
tmdb-movie-{TMDB_ID}          # movie:   tmdb-movie-535167
tmdb-show-{TMDB_ID}           # show:    tmdb-show-50878
tmdb-show-{TMDB_ID}-s{N}      # season:  tmdb-show-50878-s1
tmdb-show-{TMDB_ID}-s{N}e{N}  # episode: tmdb-show-50878-s1e1
```

### Testing with curl

```bash
# Health
curl http://localhost:5100/health

# Movie match (manual search)
curl -s -X POST http://localhost:5100/movies/library/metadata/matches \
  -H "Content-Type: application/json" \
  -d '{"type": 1, "title": "流浪地球", "year": 2019, "manual": 1}'

# Movie metadata by TMDB ID
curl http://localhost:5100/movies/library/metadata/tmdb-movie-535167

# TV show match
curl -s -X POST http://localhost:5100/tv/library/metadata/matches \
  -H "Content-Type: application/json" \
  -d '{"type": 2, "title": "甄嬛传", "year": 2011}'

# TV season children (episode list)
curl http://localhost:5100/tv/library/metadata/tmdb-show-50878-s1/children
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TMDB_API_KEY` | *(required)* | TMDB v3 API key |
| `PORT` | `5100` | Server port |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `TMDB_LANGUAGE` | `zh-CN` | Primary metadata language |
| `TMDB_FALLBACK_LANGUAGE` | `en-US` | Used when Chinese title = original title |
| `CACHE_DIR` | `./cache` | Directory for SQLite cache database |
| `CACHE_TTL` | `604800` | Cache TTL in seconds (7 days) |
| `CACHE_TTL_NOT_FOUND` | `3600` | TTL for not-found entries (1 hour) |
| `MAL_CLIENT_ID` | *(optional)* | MAL official API key — if set, uses MAL API directly instead of Jikan |

## Anime Ratings (MAL Integration)

For anime, the provider automatically looks up MAL ratings via the [Fribb/anime-lists](https://github.com/Fribb/anime-lists) TMDB→MAL mapping. No MAL API key is required — it uses the [Jikan v4](https://jikan.moe/) public API by default.

**How it works:**
1. On startup the provider downloads `anime-list-full.json` (~6 MB) and builds an in-memory TMDB ID → MAL ID index
2. For each anime item, the MAL score replaces the TMDB vote_average
3. The rating image is always `themoviedb://image.rating` (the blue TMDB badge in Plex UI)
4. Non-anime items silently fall back to TMDB vote_average

**Optional: MAL official API**

Set `MAL_CLIENT_ID` in `.env` to use the MAL official API instead of Jikan (higher rate limits, more reliable):

```bash
MAL_CLIENT_ID=your_mal_client_id
```

## Rating Sync Script

Plex's custom HTTP metadata provider API has a fundamental limitation: it **cannot directly write** `audience_rating` or `audienceRatingImage` into the Plex database. The provider can only populate the `taggings` table (the `Rating[]` array), which controls the star-rating overlay on posters — but the audience rating badge (the coloured score shown in detail views) requires separate writes to Plex.

`scripts/sync_ratings.py` bridges this gap by:

1. Reading `Rating` tag values from the Plex SQLite `taggings` table
2. Calling `PUT /library/metadata/{id}` to write `audience_rating` into `metadata_items`
3. Writing `at:audienceRatingImage` into the `extra_data` JSON blob via the bundled `Plex SQLite` binary (required because Plex uses custom FTS triggers that the system `sqlite3` cannot handle)

> ⚠️ **This script must run on the same machine as Plex Media Server** because it needs direct access to the Plex SQLite database and the `Plex SQLite` binary.

```bash
# One-time: only fix items that are missing ratings
python3 scripts/sync_ratings.py \
  --plex-host 192.168.1.x --token YOUR_PLEX_TOKEN

# Full refresh (after bulk metadata refresh or agent change)
python3 scripts/sync_ratings.py --all \
  --plex-host 192.168.1.x --token YOUR_PLEX_TOKEN

# Preview without writing
python3 scripts/sync_ratings.py --dry-run
```

**Recommended cron jobs (on the Plex server):**

```bash
# Store token — path is readable only by root
grep -oP 'PlexOnlineToken="\K[^"]+' \
  "/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/Preferences.xml" \
  | xargs -I{} sh -c 'echo "PLEX_TOKEN={}" > /etc/plex-sync.env && chmod 600 /etc/plex-sync.env'

# /etc/cron.d/plex-sync
# Weekly token refresh (Plex token is permanent but refresh just in case)
0 2 * * 0  root  /root/plex-tmdb-proxy/scripts/refresh_token.sh >> /var/log/plex-sync.log 2>&1
# Daily fast sync (only missing)
0 3 * * *  root  source /etc/plex-sync.env && cd /root/plex-tmdb-proxy && git pull -q && \
           python3 scripts/sync_ratings.py --plex-host 127.0.0.1 --token "$PLEX_TOKEN" \
           >> /var/log/plex-sync.log 2>&1
# Weekly full refresh
0 4 * * 1  root  source /etc/plex-sync.env && cd /root/plex-tmdb-proxy && \
           python3 scripts/sync_ratings.py --all --plex-host 127.0.0.1 --token "$PLEX_TOKEN" \
           >> /var/log/plex-sync.log 2>&1
```

## Known Limitations

### Ratings

| Limitation | Detail |
|------------|--------|
| **Two-step rating write** | Plex's provider API cannot write `audienceRating` directly. A separate `sync_ratings.py` run is needed after each bulk metadata refresh (see above). |
| **Rating badge image** | The badge always shows the TMDB blue logo (`themoviedb://image.rating`) even when the score comes from MAL. Plex does not support custom rating images via the provider API. |
| **Plex client display** | Some older Plex clients or web versions only display one rating entry even if multiple are provided. |
| **Jikan rate limits** | The free Jikan API allows ~3 req/s. For large anime libraries the first cold-start population may be slow; results are cached for 7 days. |

### Cast

| Limitation | Detail |
|------------|--------|
| **Show-level cast shows all seasons** | Plex displays the show-level cast list on the show detail page. We use TMDB `aggregate_credits` (union of all seasons) rather than `credits` (latest season only). For very long-running shows this can be 100+ entries. |
| **Season/episode cast is per-season** | Episode cast = season regular cast + episode guest stars merged. TMDB episode-level `credits.cast` is often empty; guest_stars contains only special appearances. |
| **No per-season aggregate** | TMDB does not provide an `aggregate_credits` equivalent for individual seasons. Season pages show the regular cast for that season only. |

### Matching

| Limitation | Detail |
|------------|--------|
| **TMDB ID only** | The provider uses TMDB IDs as primary keys. If Plex cannot auto-match a file to a TMDB entry (e.g. unusual filename), you need to manually fix the match in Plex. |
| **Multi-season anime** | Some anime series split into separate TMDB entries per cour/arc. The Fribb anime-list maps all entries; the first match (lowest MAL ID) wins for the TMDB show. |



```bash
# On your LXC (with Docker installed)
git clone https://github.com/<YOUR_USERNAME>/plex-tmdb-proxy.git
cd plex-tmdb-proxy
echo "TMDB_API_KEY=your_key_here" > .env
docker compose up -d

# Verify
curl http://$(hostname -I | awk '{print $1}'):5100/health
```

Then register the provider in Plex using the LXC's IP address.

## File Structure

```
plex-tmdb-proxy/
├── app/
│   ├── main.py              # FastAPI app entry point + health/cache routes
│   ├── config.py            # Settings via pydantic-settings + .env
│   ├── cache.py             # SQLite disk cache
│   ├── tmdb_client.py       # Async TMDB API client (movie, TV, aggregate_credits)
│   ├── metadata.py          # TMDB → Plex XML/JSON response builder
│   ├── match.py             # Match endpoint logic
│   ├── routes_movie.py      # Movie provider routes
│   ├── routes_tv.py         # TV provider routes
│   ├── utils.py             # Rating key parser
│   ├── anime_list.py        # Fribb/anime-lists downloader + TMDB→MAL index
│   ├── rating_resolver.py   # MAL-first rating resolution + apply_to_meta()
│   └── providers/
│       ├── base.py          # RatingResult dataclass
│       └── mal.py           # Jikan v4 / MAL official API client
├── scripts/
│   ├── sync_ratings.py      # Backfill audience_rating + audienceRatingImage to Plex DB
│   └── refresh_token.sh     # Read Plex token from Preferences.xml → /etc/plex-sync.env
├── tests/
│   ├── test_metadata.py         # Unit tests for metadata builder
│   ├── test_utils.py            # Unit tests for rating key parser
│   ├── test_api.py              # Integration tests for API endpoints
│   └── test_rating_resolver.py  # Unit tests for MAL rating resolver
├── cache/                   # Runtime cache (gitignored): cache.db, anime-list.json
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

## Contributing

PRs welcome. The test suite covers metadata building, rating resolution, and API endpoints:

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

## License

MIT

