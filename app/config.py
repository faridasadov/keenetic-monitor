from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "keenetic-monitor"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://keenetic:keenetic@localhost:5432/keenetic_monitor"
    fernet_key: str = Field(default="")

    collector_enabled: bool = True
    router_poll_wan_seconds: int = 60
    router_poll_clients_seconds: int = 300
    router_poll_traffic_seconds: int = 300
    router_poll_system_seconds: int = 900
    router_offline_after_failures: int = 3
    router_offline_grace_seconds: int = 30

    raw_response_dir: Path = Path("/app/raw-responses")
    save_raw_responses: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
