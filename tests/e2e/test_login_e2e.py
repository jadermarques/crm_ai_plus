from __future__ import annotations

import os
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Generator

import pytest
from playwright.sync_api import Page, expect

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_PATH = PROJECT_ROOT / "src" / "frontend" / "app.py"


def _wait_for_port(port: int, timeout: float = 15.0) -> None:
    import socket

    start = time.time()
    while time.time() - start < timeout:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1.0)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.5)
    raise TimeoutError(f"Port {port} did not open in {timeout} seconds")


@pytest.fixture(scope="session")
def e2e_env(tmp_path_factory) -> dict[str, str]:
    """Override env vars for the Streamlit process and seed a user."""
    from src.core.auth import create_user, ensure_users_table, run_async

    db_path = tmp_path_factory.mktemp("e2e") / "test.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"

    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": db_url,
            "REDIS_URL": "redis://localhost:6379/0",
            "CHROMA_HOST": "http://localhost:8000",
            "CHATWOOT_BASE_URL": "https://chatwoot.local",
            "CHATWOOT_ACCOUNT_ID": "1",
            "CHATWOOT_API_ACCESS_TOKEN": "test-token",
            "CHATWOOT_ACCESS_TOKEN": "test-token",
            "OPENAI_API_KEY": "test-key",
        }
    )

    # Seed user (override env while seeding)
    original_env = os.environ.copy()
    os.environ.update(env)

    async def _seed() -> None:
        import sqlalchemy as sa
        from src.core.database import get_sessionmaker

        await ensure_users_table()
        sm = get_sessionmaker()
        async with sm() as session:
            await session.execute(sa.text("DELETE FROM users WHERE username = :u"), {"u": "admin"})
            await session.commit()
        await create_user("admin", "secret1")

    try:
        run_async(_seed())
    finally:
        os.environ.clear()
        os.environ.update(original_env)

    return env


@pytest.fixture(scope="session")
def streamlit_server(e2e_env: dict[str, str]) -> Generator[dict[str, str], None, None]:
    """Start the Streamlit app on a test port."""
    port = 8502
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(APP_PATH),
        "--server.port",
        str(port),
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]
    proc = subprocess.Popen(cmd, env=e2e_env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        _wait_for_port(port)
        yield {"port": port}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture(scope="session")
def base_url(streamlit_server: dict[str, str]) -> str:
    return f"http://localhost:{streamlit_server['port']}"


@pytest.mark.skipif(
    os.environ.get("RUN_E2E") != "1", reason="Defina RUN_E2E=1 para rodar testes E2E (exige Playwright)."
)
@pytest.mark.e2e
def test_login_flow(page: Page, base_url: str) -> None:
    logger.info("Abrindo app em %s", base_url)
    page.goto(base_url, wait_until="networkidle")

    # Form login
    logger.info("Preenchendo credenciais de teste")
    page.get_by_label("Usuário").fill("admin")
    page.get_by_label("Senha").fill("secret1")
    page.get_by_role("button", name="Entrar").click()
    logger.info("Submeteu login, validando redirecionamento")

    # Após login, não deve ver o formulário
    expect(page.get_by_text("CRM AI Plus - Login")).to_have_count(0)
    # Deve ver Visão Geral
    expect(page.get_by_role("heading", name="Visão Geral")).to_be_visible()
    logger.info("Visão Geral visível")

    # Sidebar mostra usuário logado
    expect(page.get_by_text("admin")).to_be_visible()
    logger.info("Usuário logado exibido na sidebar")
logger = logging.getLogger("e2e.login")
