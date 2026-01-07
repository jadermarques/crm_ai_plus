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

# Helper central para rodar corrotinas em contexto Streamlit
def run_async(coro):
    return asyncio.run(coro)


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
    db_ok, db_error = asyncio.run(ping_database())
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
