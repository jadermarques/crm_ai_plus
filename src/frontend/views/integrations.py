from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.frontend.shared import page_header, render_db_status


def render() -> None:
    page_header("Integrações", "Configure Chatwoot, OpenAI, Redis e Chroma.")
    render_db_status()

    st.info("Em breve: formulários de configuração e status das integrações.")
