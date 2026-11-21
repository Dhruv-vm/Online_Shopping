# ruff: noqa: E402  -- DATABASE_URL/infra env must be set before app modules import settings.
import os
from pathlib import Path as _Path
from urllib.parse import urlsplit as _urlsplit
from urllib.parse import urlunsplit as _urlunsplit


def _read_env_database_url() -> str | None:
    """Resolve DATABASE_URL the same way Settings does (env var > .env files)."""
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    backend_dir = _Path(__file__).resolve().parent.parent
    found = None
    for env_file in (backend_dir / ".env", backend_dir.parent / ".env"):
        if not env_file.is_file():
            continue
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                found = line.split("=", 1)[1].strip().strip('"').strip("'")
    return found


def _isolated_test_database_url() -> str | None:
    """Never run the suite against a development or production database.

    The suite creates thousands of fixture rows and resets inventory, so it is
    pointed at a dedicated database: TEST_DATABASE_URL if given, otherwise the
    configured DATABASE_URL with ``_test`` appended to its database name.
    """
    url = os.environ.get("TEST_DATABASE_URL") or _read_env_database_url()
    if not url or url.startswith("sqlite"):
        return url
    parts = _urlsplit(url)
    db_name = parts.path.lstrip("/")
    if "test" not in db_name.lower():
        if os.environ.get("TEST_DATABASE_URL"):
            raise RuntimeError(
                f"TEST_DATABASE_URL must name a test database (got '{db_name}')."
            )
        db_name = f"{db_name}_test"
    return _urlunsplit(parts._replace(path="/" + db_name))


_TEST_DATABASE_URL = _isolated_test_database_url()
if _TEST_DATABASE_URL:
    os.environ["DATABASE_URL"] = _TEST_DATABASE_URL

# Safety guard: the repository .env may point at live (Aiven) Kafka/OpenSearch.
# Unit/integration tests must never write to shared infrastructure, so these are
# blanked unless a live-infrastructure run is explicitly requested.
if os.environ.get("BASKET_LIVE_INFRA_TESTS") != "1":
    os.environ["OPENSEARCH_URL"] = ""
    os.environ["KAFKA_BOOTSTRAP_SERVERS"] = ""

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.config import settings
from app.core.database import get_db_session, get_engine, reset_engine
from app.main import create_app

_catalogue_seeded = False


def _prepare_test_database() -> None:
    """Create the isolated test database if missing and migrate it to head."""
    import asyncio

    from sqlalchemy.ext.asyncio import create_async_engine

    url = settings.DATABASE_URL
    if not url or url.startswith("sqlite"):
        return
    parts = _urlsplit(url)
    db_name = parts.path.lstrip("/")
    assert "test" in db_name.lower(), f"refusing to use non-test database {db_name}"
    admin_url = _urlunsplit(parts._replace(path="/postgres"))

    async def _ensure() -> None:
        engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
        try:
            async with engine.connect() as conn:
                exists = await conn.scalar(
                    text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": db_name}
                )
                if not exists:
                    await conn.execute(text(f'CREATE DATABASE "{db_name}"'))
        finally:
            await engine.dispose()

    asyncio.run(_ensure())
    if os.environ.get("BASKET_TEST_SKIP_MIGRATE") != "1":
        from alembic.config import Config

        from alembic import command

        backend_dir = Path(__file__).resolve().parent.parent
        cfg = Config(str(backend_dir / "alembic.ini"))
        cfg.set_main_option("script_location", str(backend_dir / "alembic"))
        command.upgrade(cfg, "head")


def pytest_sessionstart(session):  # noqa: ARG001
    _prepare_test_database()


@pytest.fixture(autouse=True)
async def ensure_baseline_catalogue():
    """Ensure standard test catalogue is seeded if running on a fresh/clean database."""
    global _catalogue_seeded
    if _catalogue_seeded:
        return
    if settings.has_database and not settings.DATABASE_URL.startswith("sqlite"):
        try:
            async for session in get_db_session():
                res = await session.execute(text("SELECT count(*) FROM categories"))
                if (res.scalar() or 0) < 7:
                    from app.seeds.seed_catalogue import seed_database

                    await seed_database()
                _catalogue_seeded = True
                break
        except Exception:
            pass


@pytest.fixture(autouse=True)
async def cleanup_database_engine():
    """Ensure engine and connections are scoped to each test's event loop."""
    reset_engine()
    yield
    if settings.has_database and not settings.DATABASE_URL.startswith("sqlite"):
        try:
            async for session in get_db_session():
                await session.execute(
                    text("""
                        UPDATE store_inventory
                        SET on_hand_quantity = 50, reserved_quantity = 0
                        WHERE reserved_quantity > 0 OR on_hand_quantity < 10
                    """)
                )
                await session.commit()
                break
        except Exception:
            pass
    engine = get_engine()
    if engine is not None:
        await engine.dispose()
    reset_engine()


@pytest.fixture
def app_instance():
    return create_app()


@pytest.fixture
async def async_client(app_instance) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app_instance)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


TEST_SYNTHETIC_CA_PEM = """-----BEGIN CERTIFICATE-----
MIIDEzCCAfugAwIBAgIUElVJjmlBvBJH686VskGx6WFzWQwwDQYJKoZIhvcNAQEL
BQAwGTEXMBUGA1UEAwwOQkFTS0VUIFRlc3QgQ0EwHhcNMjYxMTE5MTAyMzEzWhcN
MzYxMTE2MTAyMzEzWjAZMRcwFQYDVQQDDA5CQVNLRVQgVGVzdCBDQTCCASIwDQYJ
KoZIhvcNAQEBBQADggEPADCCAQoCggEBAMOZaUllzRC78Ds4f8pu1MoqOWWclw/j
/tIGO2g7CPmBWux4K2FMv5K7LWZqlXxRU9er/OFmeIdBq2zf6REPGkhmIylqmMYl
h7rgt3EsiH1z7d7lzq0DYITFKJ7cLqqIKCIK8JuIUk/xaI491azPtr3azpgZXDd1
+LSElIpa3rvvk/ZDouLYxHQU/FADHwcXzjDe6sL62TVGbp+YLQAmCnTVtkSDMEXg
yZvWpjgnRUmj1lTD4M18CoQJ4TM0X172U6OJc2em9/IeumKNBHCTXlEoAjr9U9IG
ObXpFyERuTxsEOH3QZN8CFjzw7boaHwSZ5kCgZ7gPBj7BL6dunqOQkcCAwEAAaNT
MFEwHQYDVR0OBBYEFHTVJwHBftlJIGfnx/tGtg1LgMijMB8GA1UdIwQYMBaAFHTV
JwHBftlJIGfnx/tGtg1LgMijMA8GA1UdEwEB/wQFMAMBAf8wDQYJKoZIhvcNAQEL
BQADggEBABbkrZESKlYKzDuXUQII5H0N1pwaVgn2U5V7fUQ/GUuCum3DHNhfUX3b
54IC0fb8ktv0lxlF8WrxadICcL4a4vUDpz6lExkhhzElX/iFfhLEyWjt/OPvd5cV
vvV6W9q6rHc3qa3uV5wRPmb80YA/5aSn+TD0dE4HIkYJXiNS++a2Koxggm051AHw
AeCqJwf4vX8aGkdzvWbfxA5t94hQd0hkJ4Gm991A+yjCsS9pzq8Xf0YqD5VV2xsi
L1MEllMVAKf8o5Hfr7nztjiE05VCn74ek4czQBtKokUCoGXlB1Trt6I2MyCalzvC
/ztK/bOea09K8DFXzMSZc3svDOc080w=
-----END CERTIFICATE-----
"""


@pytest.fixture
def test_ca_pem_file(tmp_path: Path) -> Path:
    """Provides a syntactically valid temporary CA PEM certificate for TLS verification tests."""
    cert_path = tmp_path / "synthetic_ca.pem"
    cert_path.write_text(TEST_SYNTHETIC_CA_PEM, encoding="utf-8")
    return cert_path
