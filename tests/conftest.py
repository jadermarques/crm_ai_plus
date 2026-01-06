from __future__ import annotations

import importlib
import sys
from pathlib import Path
import asyncio
from typing import AsyncGenerator

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


@pytest.fixture(scope="function")
def test_env(monkeypatch) -> None:
    """Set required env vars for settings during tests."""
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("CHROMA_HOST", "http://localhost:8000")
    monkeypatch.setenv("CHATWOOT_BASE_URL", "https://chatwoot.local")
    monkeypatch.setenv("CHATWOOT_ACCOUNT_ID", "1")
    monkeypatch.setenv("CHATWOOT_API_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("CHATWOOT_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")


@pytest.fixture(scope="function", autouse=True)
def reset_settings_and_db(test_env) -> None:
    """Clear cached settings and DB engine/sessionmakers between tests."""
    import src.core.config as config
    import src.core.database as db

    config.get_settings.cache_clear()
    db._ENGINES.clear()
    db._SESSIONMAKERS.clear()
    importlib.reload(db)
    importlib.reload(config)


@pytest.fixture(scope="session")
def event_loop() -> asyncio.AbstractEventLoop:
    """Create an event loop for pytest-asyncio (session scope)."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module", autouse=True)
def module_file_logger(request) -> None:
    """Cria um log por módulo de teste em logs/tests/<module>.log."""
    import logging

    log_dir = Path("logs/tests")
    log_dir.mkdir(parents=True, exist_ok=True)
    module_stem = Path(request.fspath).stem
    log_path = log_dir / f"{module_stem}.log"

    handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.addHandler(handler)
    try:
        yield
    finally:
        root.removeHandler(handler)
        handler.close()
