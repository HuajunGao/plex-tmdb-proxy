# TMDB Chinese Metadata Provider for Plex

A custom metadata provider that supplies **Chinese metadata** from [TMDB](https://www.themoviedb.org/) to Plex Media Server, solving the problem of Plex's built-in agents returning English-only metadata for Chinese libraries.

## Features

- 🇨🇳 Chinese titles, summaries, and genre tags (`zh-CN`)
- 🎬 Movies (type 1) + TV shows / seasons / episodes (type 2/3/4)
- 🔤 Automatic English fallback when Chinese title equals the original
- 🖼️ Posters, backdrops, and clear logos from TMDB
- 💾 SQLite-based disk cache (7-day TTL, 1-hour TTL for not-found)
- 🐳 Docker / Docker Compose ready — deploy to any LXC or VM

## Architecture

```
Plex Media Server
      │  POST /movies/library/metadata/matches  (match)
      │  GET  /movies/library/metadata/{key}    (metadata)
      ▼
FastAPI App (port 5100)
      │
      ├─ SQLite cache  ./cache/cache.db
      │
      └─ TMDB API  api.themoviedb.org/3
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

## Deploy to Proxmox LXC

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
│   ├── main.py          # FastAPI app entry point + health/cache routes
│   ├── config.py        # Settings via pydantic-settings + .env
│   ├── cache.py         # SQLite disk cache
│   ├── tmdb_client.py   # Async TMDB API client
│   ├── metadata.py      # TMDB → Plex response builder
│   ├── match.py         # Match endpoint logic
│   ├── routes_movie.py  # Movie provider routes
│   ├── routes_tv.py     # TV provider routes
│   └── utils.py         # Rating key parser
├── tests/
│   ├── test_metadata.py # Unit tests for metadata builder
│   ├── test_utils.py    # Unit tests for rating key parser
│   └── test_api.py      # Integration tests for API endpoints
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

## License

MIT
