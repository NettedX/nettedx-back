from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from sqlalchemy import URL


class Settings(BaseSettings):
    app_name: str = "NettedX API"
    app_env: Literal["dev", "staging", "prod"] = "dev"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    jwt_secret: str = "change-me"
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_access_ttl_seconds: int = 300  # 5分钟
    jwt_refresh_ttl_seconds: int = 604800  # 7天

    siwe_domain: str = "localhost:5173"
    siwe_uri: str = "http://localhost:5173"
    siwe_statement: str = "Sign in to NettedX."
    siwe_allowed_chain_ids: str = "97"
    siwe_nonce_ttl_seconds: int = 300

    @property
    def allowed_siwe_chain_ids(self) -> set[int]:
        return {
            int(item.strip()) for item in self.siwe_allowed_chain_ids.split(",") if item.strip()
        }

    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = "nettedx"
    db_password: str = ""
    db_name: str = "nettedx"
    db_echo: bool = False

    # 构造 FastAPI 运行时使用的异步数据库 URL。
    @property
    def async_database_url(self) -> str:
        return URL.create(
            drivername="mysql+aiomysql",
            username=self.db_user,
            password=self.db_password or None,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            query={"charset": "utf8mb4"},
        ).render_as_string(hide_password=False)

    # 构造 Alembic 数据库迁移使用的同步数据库 URL。
    @property
    def sync_database_url(self) -> str:
        return URL.create(
            drivername="mysql+pymysql",
            username=self.db_user,
            password=self.db_password or None,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            query={"charset": "utf8mb4"},
        ).render_as_string(hide_password=False)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="NETTEDX_",
        extra="ignore",
    )


settings = Settings()
