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
    provider_identifier: str = "tv.plex.agents.custom.tmdb.zh"
    provider_title_movie: str = "TMDB Chinese (Movies)"
    provider_title_tv: str = "TMDB Chinese (TV Shows)"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
