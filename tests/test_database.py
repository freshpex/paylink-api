from pathlib import Path
import runpy
from unittest.mock import MagicMock

import pytest
from alembic import context
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.core.db import database_engine


@pytest.mark.parametrize("scheme", ["postgres", "postgresql", "postgresql+psycopg"])
def test_neon_connection_urls_keep_credentials_and_tls_options(scheme):
    suffix = "user:escaped%40password@database.neon.tech/app?sslmode=require&channel_binding=require"
    config = Settings(
        _env_file=None,
        database_url=f"{scheme}://{suffix}",
        database_url_unpooled=f"{scheme}://{suffix}",
    )
    assert config.database_url == f"postgresql+psycopg://{suffix}"
    assert config.database_url_unpooled == f"postgresql+psycopg://{suffix}"
    engine = database_engine(config.database_url)
    try:
        assert engine.dialect.driver == "psycopg"
        assert isinstance(engine.pool, NullPool)
        assert engine.url.query == {"sslmode": "require", "channel_binding": "require"}
    finally:
        engine.dispose()


@pytest.mark.parametrize("unpooled", ["", "postgresql://user:password@direct.neon.tech/app"])
def test_migrations_choose_direct_url_when_configured(monkeypatch, unpooled):
    from app.core import config as config_module, db

    config = Settings(
        _env_file=None,
        database_url="postgresql://user:password@pooled-pooler.neon.tech/app",
        database_url_unpooled=unpooled,
    )
    factory = MagicMock()
    monkeypatch.setattr(config_module, "settings", lambda: config)
    monkeypatch.setattr(db, "database_engine", factory)
    monkeypatch.setattr(context, "is_offline_mode", lambda: False)
    monkeypatch.setattr(context, "configure", MagicMock())
    monkeypatch.setattr(context, "begin_transaction", MagicMock())
    migrate = MagicMock()
    monkeypatch.setattr(context, "run_migrations", migrate)

    runpy.run_path(str(Path(__file__).parents[1] / "alembic" / "env.py"))

    factory.assert_called_once_with(config.database_url_unpooled or config.database_url)
    migrate.assert_called_once_with()
    factory.return_value.dispose.assert_called_once_with()
