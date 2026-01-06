from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.frontend.shared import page_header, render_db_status


def render() -> None:
    page_header("Visão Geral", "Resumo do workspace com indicadores e atividades recentes.")
    render_db_status()

    col1, col2, col3 = st.columns(3)
    col1.metric("Contatos", "0", "+0 esta semana")
    col2.metric("Oportunidades", "0", "pipeline vazio")
    col3.metric("Tarefas", "0", "nenhuma pendente")

    st.subheader("Atividades recentes")
    st.info("Em breve: feed de eventos, sincronização com Chatwoot e notas.")
