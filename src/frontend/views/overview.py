from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st
from sqlalchemy.engine import make_url

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from textwrap import dedent

from src.core.config import get_settings
from src.frontend.shared import page_header, render_db_status, run_async, ping_database


def _card_css() -> None:
    st.markdown(
        """
        <style>
        .status-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(220px, 1fr));
            gap: 14px;
            margin-top: 0.5rem;
            width: 100%;
        }
        .status-card {
            border: 1px solid #e5e7eb;
            border-radius: 14px;
            padding: 14px 16px;
            background: #fff;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            min-height: 140px;
        }
        .status-card h4 {
            margin: 0 0 8px 0;
            font-size: 17px;
            line-height: 1.3;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .status-card p {
            margin: 0 0 6px 0;
            font-size: 15px;
            line-height: 1.5;
        }
        .status-ok { color: #16a34a; }
        .status-warn { color: #d97706; }
        .status-info { color: #2563eb; }
        @media (max-width: 1200px) {
            .status-grid { grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _status_icon(status: str) -> tuple[str, str]:
    match status:
        case "ok":
            return "🟢", "status-ok"
        case "warn":
            return "🟠", "status-warn"
        case _:
            return "🔵", "status-info"


def _mask_value(value: str | None) -> str:
    if not value:
        return "não configurada"
    if len(value) <= 6:
        return "***"
    return f"{value[:3]}...{value[-2:]}"


def _format_time(tz_name: str) -> tuple[str, str, str]:
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")
    now = datetime.now(tz)
    utc_now = datetime.utcnow()
    return now.strftime("%H:%M:%S"), tz.key, utc_now.strftime("%H:%M:%S")


def _render_card(title: str, status: str, lines: list[str]) -> str:
    icon, cls = _status_icon(status)
    body = "".join(f"<p>{line}</p>" for line in lines if line)
    return dedent(
        f"""
        <div class="status-card">
            <h4 class="{cls}">{icon} {title}</h4>
            {body}
        </div>
        """
    ).strip()


def render() -> None:
    page_header("Visão Geral", "Resumo do workspace com indicadores e status.")
    render_db_status()
    _card_css()

    db_ok, db_error = run_async(ping_database())
    try:
        settings = get_settings()
    except Exception:
        settings = None

    chatwoot_url = getattr(settings, "CHATWOOT_BASE_URL", None) if settings else None
    openai_key = getattr(settings, "OPENAI_API_KEY", None) if settings else None
    timezone_name = "America/Sao_Paulo"
    hora_local, tz_local, hora_utc = _format_time(timezone_name)

    # Banco de dados: avaliar backend padrão (Postgres) e status da conexão
    backend_name = "-"
    host = "local"
    db_name = "-"
    is_postgres = False
    if settings and getattr(settings, "DATABASE_URL", None):
        try:
            parsed = make_url(settings.DATABASE_URL)
            backend_name = parsed.get_backend_name() or "-"
            host = parsed.host or "local"
            db_name = parsed.database or "-"
            is_postgres = backend_name in {"postgresql", "postgres"}
        except Exception:
            backend_name = "desconhecido"

    db_status = "ok" if db_ok and is_postgres else "warn"

    cards = [
        {
            "title": "Banco de dados",
            "status": db_status,
            "lines": [
                f"Workspace DB: {backend_name} ({db_name})",
                f"host: {host} • status: {'ativo' if db_ok else 'falha'}",
                f"Banco padrão: {'Postgres' if is_postgres else f'Não conforme ({backend_name})'}",
                "Chatwoot DB: host:",
                f"{chatwoot_url or '-'} • status: {'ativo (via API)' if chatwoot_url else 'não configurado'}",
            ],
        },
        {
            "title": "Chatwoot",
            "status": "ok" if chatwoot_url else "warn",
            "lines": [
                "Chatwoot conectado" if chatwoot_url else "Chatwoot não configurado",
                "Usuários online: 1 (mock)",
            ],
        },
        {
            "title": "OpenAI",
            "status": "ok" if openai_key else "warn",
            "lines": [
                f"OPENAI_API_KEY carregada ({_mask_value(openai_key)})",
                "Teste de modelo ignorado por incompatibilidade de proxy/cliente.",
            ],
        },
        {
            "title": "Versão do Chatwoot",
            "status": "info" if chatwoot_url else "warn",
            "lines": [
                "Versão 4.x (placeholder)",
                f"host: {chatwoot_url or '-'}",
            ],
        },
        {
            "title": "Webhook",
            "status": "warn",
            "lines": [
                "Webhook inativo",
            ],
        },
        {
            "title": "Bot",
            "status": "warn",
            "lines": [
                "Bot desativado",
            ],
        },
        {
            "title": "Hora do Chatwoot",
            "status": "ok",
            "lines": [
                f"Hora: {hora_local} • Time zone:",
                tz_local,
                f"UTC: {hora_utc}",
            ],
        },
        {
            "title": "Hora do Workspace",
            "status": "ok",
            "lines": [
                f"Hora: {hora_local} • Time zone:",
                tz_local,
                f"UTC: {hora_utc}",
            ],
        },
    ]

    cards_html = "".join(_render_card(card["title"], card["status"], card["lines"]) for card in cards)
    st.markdown(f'<div class="status-grid">{cards_html}</div>', unsafe_allow_html=True)
