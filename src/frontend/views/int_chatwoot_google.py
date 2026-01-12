"""View da integração Int. Google Ads (placeholder).

Este módulo fornece uma view placeholder para a futura integração
Chatwoot-Google Ads. Atualmente exibe uma mensagem de status de
desenvolvimento e funcionalidades planejadas.

Functions:
    render: Ponto de entrada principal para renderizar a view placeholder.

Note:
    Esta integração está em desenvolvimento. A funcionalidade real
    será implementada em uma versão futura.
"""
from __future__ import annotations

import streamlit as st

from src.frontend.shared import page_header, render_db_status


def render() -> None:
    """Renderiza a view placeholder da integração Int. Google Ads.

    Exibe uma página com informações de status de desenvolvimento
    e funcionalidades planejadas para a integração com Google Ads.
    """
    page_header("Int. Google Ads")
    render_db_status()

    st.info("🚧 **Em Desenvolvimento**")

    st.markdown("""
    Esta integração está planejada para conectar o Chatwoot ao Google Ads.

    ### Funcionalidades Planejadas

    - Rastreamento de conversões do Google Ads
    - Atribuição de leads vindos de campanhas Google
    - Relatórios de desempenho de campanhas

    ### Status

    Esta funcionalidade está em desenvolvimento e será disponibilizada em breve.
    """)
