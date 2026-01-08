from __future__ import annotations

import sys
from pathlib import Path
import asyncio

import streamlit as st
from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.database import get_engine

_SESSION_LOOP_KEY = "crm_ai_plus_event_loop"
_fallback_loop: asyncio.AbstractEventLoop | None = None

def _get_or_create_loop() -> asyncio.AbstractEventLoop:
    global _fallback_loop
    try:
        loop = st.session_state.get(_SESSION_LOOP_KEY)
        if loop is None or loop.is_closed():
            loop = asyncio.new_event_loop()
            st.session_state[_SESSION_LOOP_KEY] = loop
        return loop
    except Exception:
        if _fallback_loop is None or _fallback_loop.is_closed():
            _fallback_loop = asyncio.new_event_loop()
        return _fallback_loop


# Helper central para rodar corrotinas em contexto Streamlit
def run_async(coro):
    loop = _get_or_create_loop()
    if loop.is_running():
        raise RuntimeError("run_async nao pode ser chamado com loop em execucao.")
    return loop.run_until_complete(coro)


async def ping_database() -> tuple[bool, str | None]:
    engine = None
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:
        return False, str(exc)
    finally:
        if engine is not None:
            try:
                await engine.dispose()
            except Exception:
                pass


def render_db_status() -> None:
    db_ok, db_error = run_async(ping_database())
    if db_ok:
        return
    else:
        message = "Banco de Dados: falha ao conectar"
        if db_error:
            message = f"{message} ({db_error})"
        st.error(message, icon="⚠️")


def page_header(title: str, subtitle: str | None = None) -> None:
    st.title(title)
    if subtitle:
        st.caption(subtitle)
