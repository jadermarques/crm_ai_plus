from __future__ import annotations

import sys
from pathlib import Path
import re

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.auth import (
    create_user,
    ensure_users_table,
    list_users,
    set_user_status,
    update_user,
)
from src.frontend.shared import page_header, render_db_status, run_async

_EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}(?:\.[^@\s]{2,})?$")


def render() -> None:
    page_header("Usuários", "Gerencie usuários do workspace.")
    render_db_status()
    run_async(ensure_users_table())

    if "users_selected_id" not in st.session_state:
        st.session_state.users_selected_id = None

    st.caption("Inclua, edite ou desabilite usuários. Exclusão física não é permitida.")

    users_data = run_async(list_users())
    selected = None
    if st.session_state.users_selected_id is not None:
        selected = next(
            (u for u in users_data if u["id"] == st.session_state.users_selected_id), None
        )
        if selected is None:
            st.session_state.users_selected_id = None

    _render_user_form(selected)
    st.divider()
    _render_user_list(users_data)


def _render_user_form(selected: dict | None) -> None:
    is_edit = selected is not None
    st.subheader("Cadastro de usuário" if not is_edit else "Editar usuário")
    help_text = "Usuário desabilitado não consegue acessar; reabilite quando necessário."
    role_options = ["ADMIN", "USER"]
    with st.form("user_form"):
        username = st.text_input(
            "Usuário (3 a 20 caracteres, será convertido para minúsculas)",
            value=selected["username"] if is_edit else "",
        )
        full_name = st.text_input("Nome completo", value=selected.get("full_name", "") if is_edit else "")
        email = st.text_input("E-mail", value=selected.get("email", "") if is_edit else "")
        role = st.selectbox(
            "Tipo de usuário",
            role_options,
            index=role_options.index(selected.get("role", "USER")) if is_edit else 1,
            help="Selecione ADMIN ou USER.",
        )
        password = st.text_input(
            "Senha (mínimo 6 caracteres)",
            type="password",
            value="",
            help="Deixe em branco para não alterar a senha ao editar.",
        )
        confirm_password = st.text_input(
            "Confirmar senha",
            type="password",
            value="",
            help="Obrigatório ao criar ou se alterar a senha.",
        )
        is_active = st.checkbox(
            "Usuário ativo",
            value=selected.get("is_active", True) if is_edit else True,
            help=help_text,
        )
        submitted = st.form_submit_button("Atualizar usuário" if is_edit else "Criar usuário")

    if not submitted:
        return

    normalized_username = username.strip().lower()
    if len(normalized_username) < 3 or len(normalized_username) > 20:
        st.error("O usuário deve ter entre 3 e 20 caracteres (minúsculas).")
        return
    if not normalized_username:
        st.error("Informe um usuário válido.")
        return
    if not full_name.strip():
        st.error("Informe o nome completo.")
        return
    if not email.strip() or not _EMAIL_REGEX.match(email.strip().lower()):
        st.error("Informe um e-mail válido.")
        return

    is_new_password = bool(password or confirm_password)
    if is_edit:
        if is_new_password:
            if len(password) < 6:
                st.error("A senha deve ter pelo menos 6 caracteres.")
                return
            if password != confirm_password:
                st.error("As senhas não conferem.")
                return
        try:
            run_async(
                update_user(
                    selected["id"],
                    username=normalized_username,
                    full_name=full_name,
                    email=email,
                    password=password if is_new_password else None,
                    is_active=is_active,
                    role=role,
                )
            )
            st.success("Usuário atualizado com sucesso.")
            st.session_state.users_selected_id = None
            st.rerun()
        except Exception as exc:
            st.error(f"Erro ao atualizar usuário: {exc}")
    else:
        if len(password) < 6:
            st.error("A senha deve ter pelo menos 6 caracteres.")
            return
        if password != confirm_password:
            st.error("As senhas não conferem.")
            return
        try:
            run_async(
                create_user(
                    username=normalized_username,
                    password=password,
                    full_name=full_name,
                    email=email,
                    role=role,
                )
            )
            st.success("Usuário criado com sucesso.")
            st.session_state.users_selected_id = None
            st.rerun()
        except Exception as exc:
            st.error(f"Erro ao criar usuário: {exc}")


def _render_user_list(users_data: list[dict]) -> None:
    st.subheader("Usuários cadastrados")
    if not users_data:
        st.info("Nenhum usuário cadastrado ainda.")
        return

    header_cols = st.columns([2, 2.6, 3, 1.6, 1.6, 2])
    header_cols[0].markdown("**Usuário**")
    header_cols[1].markdown("**Nome**")
    header_cols[2].markdown("**E-mail**")
    header_cols[3].markdown("**Tipo**")
    header_cols[4].markdown("**Status**")
    header_cols[5].markdown("**Ações**")

    for user in users_data:
        cols = st.columns([2, 2.6, 3, 1.6, 1.6, 2])
        cols[0].write(user.get("username") or "-")
        cols[1].write(user.get("full_name") or "-")
        cols[2].write(user.get("email") or "-")
        cols[3].write(user.get("role") or "USER")
        status = "Ativo" if user.get("is_active", True) else "Desabilitado"
        status_icon = "🟢" if user.get("is_active", True) else "⭕️"
        cols[4].write(f"{status_icon} {status}")
        actions_col = cols[5]
        edit_key = f"edit_{user['id']}"
        toggle_key = f"toggle_{user['id']}"
        if actions_col.button("Editar", key=edit_key, use_container_width=True):
            st.session_state.users_selected_id = user["id"]
            st.rerun()
        toggle_label = "Desabilitar" if user.get("is_active", True) else "Habilitar"
        if actions_col.button(toggle_label, key=toggle_key, use_container_width=True):
            try:
                run_async(set_user_status(user["id"], not user.get("is_active", True)))
                action_text = "desabilitado" if toggle_label == "Desabilitar" else "habilitado"
                st.success(f"Usuário {action_text} com sucesso.")
                st.rerun()
            except Exception as exc:
                st.error(f"Erro ao atualizar status: {exc}")

    if st.session_state.users_selected_id is not None:
        if st.button("Cancelar edição", type="secondary"):
            st.session_state.users_selected_id = None
            st.rerun()
