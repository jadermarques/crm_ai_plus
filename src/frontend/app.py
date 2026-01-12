"""CRM AI Plus - Aplicação Principal Streamlit.

Este módulo fornece o ponto de entrada principal para a aplicação web CRM AI Plus.
Trata autenticação de usuários, navegação e roteamento de views.

Attributes:
    LOG_APP_METRICS: Habilita logging de métricas de performance.
    AUTO_LOGIN_ENABLED: Habilita auto-login para desenvolvimento.
    AUTO_LOGIN_USER: Nome de usuário para auto-login.

Functions:
    main: Ponto de entrada principal da aplicação.
    render_login_flow: Renderiza o fluxo de autenticação.
    render_sidebar_navigation: Renderiza o menu lateral.
    render_placeholder: Renderiza conteúdo placeholder para views não implementadas.

Usage:
    Execute com Streamlit::

        streamlit run src/frontend/app.py
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.frontend.views import overview, users
from src.frontend.views import agents as agents_view
from src.frontend.views import bots as bots_view
from src.frontend.views import bot_tests as bot_tests_view
from src.frontend.views import modules as modules_view
from src.frontend.views import applications as applications_view
from src.frontend.views import permissions as permissions_view
from src.frontend.views import ia_configs as ia_configs_view
from src.frontend.views import bot_simulator as bot_simulator_view
from src.frontend.views import rag_management as rag_management_view
from src.frontend.services.auth_service import (
    check_credentials,
    create_first_user,
    ensure_setup,
    get_user_count,
)
from src.frontend.views import chatwoot_params, chatwoot_connection
from src.frontend.views import int_chatwoot_meta, int_chatwoot_google
from src.frontend.config.ui_structure import MODULES, PLACEHOLDER_CONTENT, APP_LABELS

st.set_page_config(page_title="CRM AI Plus", layout="wide")
LOG_APP_METRICS = os.getenv("LOG_APP_METRICS", "").lower() in {"1", "true", "yes", "on"}
AUTO_LOGIN_ENABLED = os.getenv("DEV_AUTO_LOGIN", "").lower() in {"1", "true", "yes", "on"}
AUTO_LOGIN_USER = os.getenv("DEV_AUTO_LOGIN_USER", "").strip()
_EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}(?:\.[^@\s]{2,})?$")

# Estilo para botões da navegação na sidebar (parecendo links)
st.markdown(
    """
    <style>
    section[data-testid="stSidebar"] details {
        border: none !important;
        box-shadow: none !important;
        background: transparent !important;
    }
    section[data-testid="stSidebar"] details > summary {
        padding: 0.25rem 0.35rem;
        border: none !important;
        box-shadow: none !important;
        font-size: 1.25rem !important;
        line-height: 1.35 !important;
        font-weight: 700;
    }
    section[data-testid="stSidebar"] details > summary span {
        font-size: inherit !important;
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
    }
    section[data-testid="stSidebar"] details [data-testid="stVerticalBlock"] {
        gap: 0.1rem;
    }
    section[data-testid="stSidebar"] .stButton {
        margin: 0 !important;
    }
    section[data-testid="stSidebar"] .stButton > button {
        border: none !important;
        box-shadow: none !important;
        text-align: left;
        justify-content: flex-start;
        padding: 0.1rem 0.45rem;
        border-radius: 10px;
        width: 100%;
        margin: 0;
        font-weight: 600;
        background: transparent;
        color: #1f2937;
        min-height: 0 !important;
        height: auto !important;
        line-height: 1.2;
    }
    section[data-testid="stSidebar"] .stButton > button > div {
        padding: 0 !important;
    }
    section[data-testid="stSidebar"] .stButton > button > div {
        justify-content: flex-start;
    }
    section[data-testid="stSidebar"] .stButton > button > div > p {
        margin: 0;
        width: 100%;
        text-align: left;
    }
    section[data-testid="stSidebar"] .stButton > button[data-testid="baseButton-secondary"]:hover {
        background: #e5e7eb;
    }
    section[data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"] {
        background: #edf2ff;
        color: #111827;
    }
    section[data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"]:hover {
        background: #e0e7ff;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


if "active_app" not in st.session_state:
    st.session_state.active_app = MODULES[0]["apps"][0]["id"]


def render_sidebar_navigation() -> None:
    """Renderiza o menu de navegação lateral.

    Exibe seções expansíveis para cada módulo com botões para
    cada aplicação. Atualiza o estado da sessão quando uma app é selecionada.
    """
    st.write("### Workspace")
    for module in MODULES:
        with st.expander(f"{module['icon']} {module['label']}", expanded=False):
            for app in module["apps"]:
                is_active = st.session_state.active_app == app["id"]
                clicked = st.button(
                    app["label"],
                    key=f"btn_{module['id']}_{app['id']}",
                    type="primary" if is_active else "secondary",
                    use_container_width=True,
                )
                if clicked:
                    st.session_state.active_app = app["id"]


def render_placeholder(app_id: str) -> None:
    """Renderiza conteúdo placeholder para views não implementadas.

    Args:
        app_id: ID da aplicação para renderizar placeholder.
    """
    label = APP_LABELS.get(app_id, "Em breve")
    content = PLACEHOLDER_CONTENT.get(app_id)
    st.header(label)
    if content and content.get("desc"):
        st.caption(content["desc"])
    sections = content.get("sections") if content else []
    if not sections:
        st.info("Em breve: conteúdo para este módulo.")
        return
    for section in sections:
        st.subheader(section.get("title", label))
        st.write(section.get("body", "Em breve."))



def _validate_first_user_form(
    username: str, full_name: str, email: str, password: str, confirm_password: str
) -> str | None:
    """Valida campos do formulário de registro do primeiro usuário.

    Args:
        username: Nome de usuário (3-20 caracteres, será convertido para minúsculas).
        full_name: Nome completo do usuário.
        email: Endereço de e-mail.
        password: Senha (mínimo 6 caracteres).
        confirm_password: Confirmação da senha.

    Returns:
        Mensagem de erro se a validação falhar, None se válido.
    """
    normalized_username = username.strip().lower()
    if len(normalized_username) < 3 or len(normalized_username) > 20:
        return "Usuário deve ter entre 3 e 20 caracteres (minúsculas)."
    if len(password) < 6:
        return "A senha deve ter pelo menos 6 caracteres."
    if not normalized_username:
        return "Informe um usuário válido."
    if not full_name.strip():
        return "Informe o nome completo."
    if not email.strip():
        return "Informe um e-mail válido."
    if not _EMAIL_REGEX.match(email.strip().lower()):
        return "Informe um e-mail válido."
    if password != confirm_password:
        return "As senhas não conferem."
    return None


def _render_first_user_form() -> None:
    """Renderiza e trata o formulário de criação do primeiro usuário.

    Exibe um formulário para criar o usuário administrador inicial quando
    não existem usuários no sistema. Após envio bem-sucedido, cria o
    usuário e o autentica.
    """
    st.caption("Crie o primeiro usuário para acessar o workspace.")
    with st.form("create_first_user"):
        username = st.text_input("Usuário (3 a 20 caracteres, será convertido para minúsculas)")
        full_name = st.text_input("Nome completo")
        email = st.text_input("E-mail")
        password = st.text_input("Senha (mínimo 6 caracteres)", type="password")
        confirm_password = st.text_input("Confirmar senha", type="password")
        submitted = st.form_submit_button("Criar usuário e entrar")
        if submitted:
            error = _validate_first_user_form(username, full_name, email, password, confirm_password)
            if error:
                st.error(error)
            else:
                try:
                    create_first_user(
                        username=username.strip().lower(),
                        password=password,
                        full_name=full_name,
                        email=email,
                    )
                    st.session_state.authenticated_user = username.strip()
                    st.session_state.active_app = "overview"
                    st.rerun()
                except Exception as exc:
                    st.error(f"Erro ao criar usuário: {exc}")


def _render_login_form() -> None:
    """Renderiza e trata o formulário de login.

    Exibe campos de usuário e senha. Após autenticação bem-sucedida,
    armazena o usuário no estado da sessão e redireciona para a página inicial.
    """
    with st.form("login_form"):
        username = st.text_input("Usuário")
        password = st.text_input("Senha", type="password")
        submitted = st.form_submit_button("Entrar")
        if submitted:
            ok, user = check_credentials(username.strip().lower(), password)
            if ok:
                st.session_state.authenticated_user = user
                st.session_state.active_app = "overview"
                st.rerun()
            st.error("Usuário ou senha inválidos ou usuário desabilitado.")


def render_login_flow() -> bool:
    """Renderiza o fluxo completo de login/registro.

    Se não existirem usuários, mostra o formulário de registro do primeiro usuário.
    Caso contrário, mostra o formulário de login.

    Returns:
        True se o usuário está autenticado, False caso contrário.
    """
    ensure_setup()
    user_count = get_user_count()

    login_area = st.container()
    with login_area:
        st.header("CRM AI Plus - Login")
        if user_count == 0:
            _render_first_user_form()
        else:
            _render_login_form()
    return False


# View dispatch dictionary for reducing complexity in main()
_VIEW_DISPATCH = {
    "overview": overview.render,
    "users": users.render,
    "agents": agents_view.render,
    "bots": bots_view.render,
    "bot_tests": bot_tests_view.render,
    "modules": modules_view.render,
    "apps": applications_view.render,
    "permissions": permissions_view.render,
    "ia_configs": ia_configs_view.render,
    "rag_management": rag_management_view.render,
    "bot_simulator": bot_simulator_view.render,
    "chatwoot_params": chatwoot_params.render,
    "chatwoot_connection": chatwoot_connection.render,
    "int_chatwoot_meta": int_chatwoot_meta.render,
    "int_chatwoot_google": int_chatwoot_google.render,
}


def main() -> None:
    """Ponto de entrada principal da aplicação.

    Trata inicialização do estado de autenticação, auto-login para desenvolvimento,
    renderização da sidebar e roteamento de views baseado na aplicação ativa.
    """
    if "authenticated_user" not in st.session_state:
        st.session_state.authenticated_user = None

    if AUTO_LOGIN_ENABLED and not st.session_state.authenticated_user:
        ensure_setup()
        st.session_state.authenticated_user = AUTO_LOGIN_USER or "dev"

    if not st.session_state.authenticated_user:
        authed = render_login_flow()
        if not authed:
            return

    with st.sidebar:
        st.markdown(f"👤 **{st.session_state.authenticated_user}**")
        if st.button("Sair", type="secondary", use_container_width=True):
            st.session_state.authenticated_user = None
            st.rerun()
        st.markdown("---")
        render_sidebar_navigation()

    if "active_app" not in st.session_state or st.session_state.active_app not in APP_LABELS:
        st.session_state.active_app = "overview"

    active = st.session_state.active_app
    label = APP_LABELS.get(active, active)
    start = time.perf_counter()
    try:
        render_fn = _VIEW_DISPATCH.get(active, lambda: render_placeholder(active))
        render_fn()
        if LOG_APP_METRICS:
            elapsed_ms = (time.perf_counter() - start) * 1000
            print(f"[APP] Renderizou '{label}' em {elapsed_ms:.2f} ms")
    except Exception as exc:
        if LOG_APP_METRICS:
            print(f"[APP] Erro ao renderizar '{label}': {exc}")
        raise


main()
