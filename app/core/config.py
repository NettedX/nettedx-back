from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "NettedX API"
    app_env: Literal["dev", "staging", "prod"] = "dev"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    jwt_secret: str = "change-me"
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_access_ttl_seconds: int = 300  # 5分钟
    jwt_refresh_ttl_seconds: int = 604800  # 7天

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="NETTEDX_",
        extra="ignore",
    )


settings = Settings()
