"""配置 Alembic 数据库迁移环境。"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.db.models import Base

# Alembic 当前运行使用的配置对象。
config = context.config

# 使用 alembic.ini 中定义的日志配置。
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 数据库地址来自本地 .env，不在 alembic.ini 中保存用户名和密码。
# ConfigParser 会把百分号视为插值符号，因此需要转义为两个百分号。
config.set_main_option(
    "sqlalchemy.url",
    settings.sync_database_url.replace("%", "%%"),
)

# Alembic 根据这些 ORM 元数据检测表结构变化。
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """在不创建数据库连接的情况下生成迁移 SQL。"""

    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """连接数据库并执行迁移。"""

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
