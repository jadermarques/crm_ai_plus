from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.frontend.views import (
    companies,
    contacts,
    deals,
    integrations,
    overview,
    permissions,
    tasks,
    users,
)
from src.core.auth import (
    count_users,
    create_user,
    ensure_users_table,
    run_async,
    verify_credentials,
)

st.set_page_config(page_title="CRM AI Plus", layout="wide")

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

MODULES = [
    {
        "id": "workspace",
        "label": "Workspace",
        "icon": "🗂️",
        "apps": [
            {"id": "overview", "label": "Visão Geral"},
            {"id": "contacts", "label": "Contatos"},
            {"id": "companies", "label": "Empresas"},
            {"id": "deals", "label": "Oportunidades"},
            {"id": "tasks", "label": "Tarefas"},
        ],
    },
    {
        "id": "settings",
        "label": "Configurações",
        "icon": "⚙️",
        "apps": [
            {"id": "users", "label": "Usuários"},
            {"id": "permissions", "label": "Permissões"},
            {"id": "integrations", "label": "Integrações"},
        ],
    },
]

VIEW_MAP = {
    "overview": overview.render,
    "contacts": contacts.render,
    "companies": companies.render,
    "deals": deals.render,
    "tasks": tasks.render,
    "users": users.render,
    "permissions": permissions.render,
    "integrations": integrations.render,
}

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


def render_login_flow() -> bool:
    """Returns True if authenticated."""
    # Ensure auth table exists
    run_async(ensure_users_table())
    user_count = run_async(count_users())

    login_area = st.container()
    with login_area:
        st.header("CRM AI Plus - Login")
        if user_count == 0:
            st.caption("Crie o primeiro usuário para acessar o workspace.")
            with st.form("create_first_user"):
                username = st.text_input("Usuário")
                password = st.text_input("Senha (mínimo 6 caracteres)", type="password")
                submitted = st.form_submit_button("Criar usuário e entrar")
                if submitted:
                    if len(password) < 6:
                        st.error("A senha deve ter pelo menos 6 caracteres.")
                    elif not username.strip():
                        st.error("Informe um usuário válido.")
                    else:
                        try:
                            run_async(create_user(username.strip(), password))
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
                    ok, user = run_async(verify_credentials(username.strip(), password))
                    if ok:
                        st.session_state.authenticated_user = user["username"]
                        st.session_state.active_app = "overview"
                        st.rerun()
                    st.error("Usuário ou senha inválidos.")
    return False


def main() -> None:
    if "authenticated_user" not in st.session_state:
        st.session_state.authenticated_user = None

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
    if "active_app" not in st.session_state or st.session_state.active_app not in VIEW_MAP:
        st.session_state.active_app = "overview"

    active = st.session_state.active_app
    render_fn = VIEW_MAP.get(active)
    if render_fn:
        render_fn()
    else:
        st.write("Seleção inválida.")


if __name__ == "__main__":
    main()
else:
    main()
