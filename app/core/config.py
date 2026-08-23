from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

# 项目根目录，即 nettedx-back。
BASE_DIR = Path(__file__).resolve().parents[2]
# 将本地 .env 中的配置加载到系统环境变量。
# override=False 表示部署服务器设置的环境变量拥有更高优先级。
load_dotenv(BASE_DIR / ".env", override=False)


class Settings(BaseSettings):
    app_name: str = "NettedX API"
    app_env: Literal["dev", "staging", "prod"] = "dev"
    debug: bool = True
    api_v1_prefix: str = "/v1"

    cors_allowed_origins: str = "http://localhost:5173,https://nettedx.com"

    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_seconds: int = 300  # 5分钟
    jwt_refresh_ttl_seconds: int = 604800  # 7天

    siwe_domain: str = "localhost:5173"
    siwe_uri: str = "http://localhost:5173"
    siwe_statement: str = "Sign in to NettedX."

    @property
    def allowed_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    siwe_allowed_chain_ids: str = "31337"
    siwe_nonce_ttl_seconds: int = 300

    # Blockchain
    blockchain_rpc_url: str = ""  # 后端连接区块链节点的地址
    blockchain_relayer_private_key: str = ""  # 可选；为空时开发环境使用节点解锁账户
    blockchain_transaction_timeout_seconds: int = Field(default=30, gt=0)
    netting_contract_address: str = ""  # 部署后的Netting合约地址
    mock_usdc_contract_address: str = ""
    mock_bond_contract_address: str = ""
    settlement_contract_address: str = ""
    liquidity_buffer_contract_address: str = ""
    netting_deployment_block: int = Field(default=0, ge=0)
    blockchain_event_scan_chunk_size: int = Field(default=2_000, gt=0)
    blockchain_event_confirmations: int = Field(default=0, ge=0)
    cash_token_decimals: int = Field(
        default=6, ge=0
    )  # 现金代币精度，例如 USDC 通常为 6，用于把链上最小单位换算成首页展示金额
    bond_token_decimals: int = Field(default=0, ge=0)

    # 数据库
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = "nettedx"
    db_password: str = ""
    db_name: str = "nettedx"
    db_echo: bool = False

    @property
    def allowed_siwe_chain_ids(self) -> set[int]:
        return {
            int(item.strip()) for item in self.siwe_allowed_chain_ids.split(",") if item.strip()
        }

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
        env_prefix="NETTEDX_",
        extra="ignore",
    )


settings = Settings()
