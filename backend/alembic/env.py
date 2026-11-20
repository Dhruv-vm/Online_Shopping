import asyncio
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Ensure app is discoverable on python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app.core.events.inbox  # noqa: F401
import app.modules.auctions.models  # noqa: F401
import app.modules.cart.models  # noqa: F401
import app.modules.catalogue.models  # noqa: F401
import app.modules.community.models  # noqa: F401
import app.modules.data_quality.models  # noqa: F401
import app.modules.demand.models  # noqa: F401
import app.modules.exchange.models  # noqa: F401
import app.modules.i18n.models  # noqa: F401
import app.modules.identity.models  # noqa: F401
import app.modules.intent.models  # noqa: F401
import app.modules.inventory.models  # noqa: F401
import app.modules.missions.models  # noqa: F401
import app.modules.negotiation.models  # noqa: F401
import app.modules.orders.models  # noqa: F401
import app.modules.passport.models  # noqa: F401
import app.modules.payments.models  # noqa: F401
import app.modules.price_intel.models  # noqa: F401
import app.modules.pricing.models  # noqa: F401
import app.modules.sale_stream.models  # noqa: F401
from app.core.config import settings
from app.core.database import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    if settings.DATABASE_URL:
        return settings.DATABASE_URL
    # Fallback to config value or default
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        raise ValueError(
            "DATABASE_URL is not set in environment or alembic.ini. "
            "Please configure your Aiven PostgreSQL URL in .env."
        )
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode using async engine."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connect_args = {}
    if get_url().startswith("postgresql") and settings.DATABASE_SSL_MODE.lower() in (
        "require",
        "verify-ca",
        "verify-full",
    ):
        import ssl

        ssl_ctx = ssl.create_default_context()
        if settings.DATABASE_SSL_MODE.lower() == "require":
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ssl_ctx

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
