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
from src.core.debug_logger import create_log_session

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
        # Fallback: se o loop principal estiver ocupado/rodando,
        # cria um loop temporário isolado para executar esta corrotina.
        # WARNING: Se a corrotina depender de asyncio.get_running_loop(), isso vai falhar.
        # Idealmente usamos nest_asyncio.
        import asyncio
        temp_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(temp_loop)
        try:
            return temp_loop.run_until_complete(coro)
        finally:
            temp_loop.close()
            asyncio.set_event_loop(loop) # Restore original
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


def render_debug_panel(key_suffix: str = "global", location: str = "bottom") -> Path | None:
    """
    Renders a standardized Debug Panel.
    Args:
        key_suffix: Unique suffix for widget keys.
        location: layout hint (unused for now, simplifies to bottom container).
    Returns:
        Path to log file if enabled, None otherwise.
        
    Usage:
        log_path = render_debug_panel("my_view")
    """
    st.divider()
    with st.expander("🛠 Configurações e Logs de Debug", expanded=False):
        c1, c2 = st.columns([1, 3])
        enable_full_debug = c1.checkbox(
            "Log debug completo", 
            value=False, 
            key=f"full_debug_{key_suffix}", 
            help="Salva logs detalhados em logs/debug_runs/"
        )
        
        path_key = f"debug_log_path_{key_suffix}"
        
        if enable_full_debug:
            if path_key not in st.session_state or not st.session_state[path_key]:
                st.session_state[path_key] = create_log_session()
                # st.toast(f"Log iniciado: {Path(st.session_state[path_key]).name}")
            
            c2.info(f"Log ativo: `{Path(st.session_state[path_key]).name}`")
            return st.session_state[path_key]
        else:
            st.session_state[path_key] = None
            return None
