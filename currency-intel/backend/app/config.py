from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    app_name: str = "Currency Intelligence API"
    database_url: str = f"sqlite:///{(Path(__file__).resolve().parent.parent / 'data.db').as_posix()}"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    http_timeout_seconds: float = 12.0
    cache_latest_ttl_seconds: int = 300
    cache_historical_ttl_seconds: int = 3600
    request_max_retries: int = 2

    class Config:
        env_file = ".env"
        env_prefix = "CI_"


settings = Settings()
