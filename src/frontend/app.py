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
    st.write("### Workspace")
    for module in MODULES:
        options = [app["id"] for app in module["apps"]]
        default_index = (
            options.index(st.session_state.active_app)
            if st.session_state.active_app in options
            else 0
        )
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



def render_login_flow() -> bool:
    """Returns True if authenticated."""
    # Ensure auth table exists
    ensure_setup()
    user_count = get_user_count()

    login_area = st.container()
    with login_area:
        st.header("CRM AI Plus - Login")
        if user_count == 0:
            st.caption("Crie o primeiro usuário para acessar o workspace.")
            with st.form("create_first_user"):
                username = st.text_input("Usuário (3 a 20 caracteres, será convertido para minúsculas)")
                full_name = st.text_input("Nome completo")
                email = st.text_input("E-mail")
                password = st.text_input("Senha (mínimo 6 caracteres)", type="password")
                confirm_password = st.text_input("Confirmar senha", type="password")
                submitted = st.form_submit_button("Criar usuário e entrar")
                if submitted:
                    normalized_username = username.strip().lower()
                    if len(normalized_username) < 3 or len(normalized_username) > 20:
                        st.error("Usuário deve ter entre 3 e 20 caracteres (minúsculas).")
                    elif len(password) < 6:
                        st.error("A senha deve ter pelo menos 6 caracteres.")
                    elif not normalized_username:
                        st.error("Informe um usuário válido.")
                    elif not full_name.strip():
                        st.error("Informe o nome completo.")
                    elif not email.strip():
                        st.error("Informe um e-mail válido.")
                    elif not _EMAIL_REGEX.match(email.strip().lower()):
                        st.error("Informe um e-mail válido.")
                    elif password != confirm_password:
                        st.error("As senhas não conferem.")
                    else:
                        try:
                            create_first_user(
                                username=normalized_username,
                                password=password,
                                full_name=full_name,
                                email=email,
                            )
                            st.session_state.authenticated_user = username.strip()
                            st.session_state.active_app = "overview"
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Erro ao criar usuário: {exc}")
        else:
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
    return False


def main() -> None:
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

    # Garante que após login a página ativa seja a visão geral
    if "active_app" not in st.session_state or st.session_state.active_app not in APP_LABELS:
        st.session_state.active_app = "overview"

    active = st.session_state.active_app
    label = APP_LABELS.get(active, active)
    start = time.perf_counter()
    try:
        if active == "overview":
            overview.render()
        elif active == "users":
            users.render()
        elif active == "agents":
            agents_view.render()
        elif active == "bots":
            bots_view.render()
        elif active == "bot_tests":
            bot_tests_view.render()
        elif active == "modules":
            modules_view.render()
        elif active == "apps":
            applications_view.render()
        elif active == "permissions":
            permissions_view.render()
        elif active == "ia_configs":
            ia_configs_view.render()
        elif active == "rag_management":
            rag_management_view.render()
        elif active == "bot_simulator":
            bot_simulator_view.render()
        elif active == "chatwoot_params":
            chatwoot_params.render()
        elif active == "chatwoot_connection":
            chatwoot_connection.render()
        else:
            render_placeholder(active)
        if LOG_APP_METRICS:
            elapsed_ms = (time.perf_counter() - start) * 1000
            print(f"[APP] Renderizou '{label}' em {elapsed_ms:.2f} ms")
    except Exception as exc:
        if LOG_APP_METRICS:
            print(f"[APP] Erro ao renderizar '{label}': {exc}")
        raise


if __name__ == "__main__":
    main()
else:
    main()
