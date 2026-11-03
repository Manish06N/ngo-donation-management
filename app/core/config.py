from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Values that change between a laptop and a server. They come from the environment."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "NGO Donation, Volunteer & Community Project Management"
    app_env: str = "development"
    debug: bool = False
    secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    password_reset_minutes: int = 30
    password_hash_rounds: int = 12
    database_url: str = "sqlite:///./ngo.db"
    auto_seed: bool = False
    admin_email: str = "admin@ngo.local"
    admin_password: str = ""
    admin_name: str = "Super Admin"
    cors_origins: str = "*"
    deadline_warning_days: int = 7


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
