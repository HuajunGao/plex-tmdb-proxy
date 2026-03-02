from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    tmdb_api_key: str = ""
    port: int = 5100
    log_level: str = "INFO"
    cache_dir: str = "./cache"
    cache_ttl: int = 86400 * 7  # 7 days
    cache_ttl_not_found: int = 3600  # 1 hour
    tmdb_language: str = "zh-CN"
    tmdb_fallback_language: str = "en-US"
    tmdb_image_base: str = "https://image.tmdb.org/t/p/original"
    provider_identifier: str = "tv.plex.agents.custom.tmdb.zh"  # kept for backward compat
    provider_identifier_movie: str = "tv.plex.agents.custom.tmdb.zh.movies"
    provider_identifier_tv: str = "tv.plex.agents.custom.tmdb.zh.series"
    provider_title_movie: str = "TMDB Chinese (Movies)"
    provider_title_tv: str = "TMDB Chinese (TV Shows)"
    # Optional: MAL official API client_id (https://myanimelist.net/apiconfig)
    # If not set, Jikan v4 (no key needed) is used automatically.
    mal_client_id: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
