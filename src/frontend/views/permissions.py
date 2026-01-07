from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.auth import list_users
from src.core.management import (
    create_permission,
    ensure_management_tables,
    list_applications,
    list_modules,
    list_permissions,
)
from src.frontend.shared import page_header, render_db_status, run_async


def render() -> None:
    page_header("Permissões", "Controle de acesso por módulo e aplicação.")
    render_db_status()
    run_async(ensure_management_tables())

    modules_data = run_async(list_modules(include_inactive=False))
    apps_data = run_async(list_applications(include_inactive=False))
    users_data = run_async(list_users(include_inactive=False))

    st.caption("Usuários ADMIN possuem acesso total e não precisam de permissões específicas.")
    _render_permission_form(modules_data, apps_data, users_data)
    st.divider()
    _render_permission_list(users_data, modules_data, apps_data)


def _render_permission_form(
    modules_data: list[dict], apps_data: list[dict], users_data: list[dict]
) -> None:
    st.subheader("Vincular permissão")
    user_lookup = {
        u["username"]: u
        for u in users_data
        if u.get("is_active", True) and u.get("role", "USER") != "ADMIN"
    }
    user_options = {name: data["id"] for name, data in user_lookup.items()}

    if not user_options:
        st.info("Cadastre um usuário ativo não-ADMIN para criar permissões.")
        return

    active_modules = {m["id"]: m["name"] for m in modules_data if m.get("is_active", True)}
    grouped_apps: dict[int, list[dict]] = {}
    for app in apps_data:
        if not app.get("is_active", True):
            continue
        if app["module_id"] not in active_modules:
            continue
        grouped_apps.setdefault(app["module_id"], []).append(app)

    with st.form("permission_form"):
        user_name = st.selectbox("Usuário", list(user_options.keys()))
        selected_app_ids: list[int] = []
        user_role = user_lookup.get(user_name, {}).get("role", "USER")

        if user_role == "ADMIN":
            st.info("Usuário ADMIN já possui acesso a todos os módulos e aplicações.")
        elif not grouped_apps:
            st.warning("Cadastre módulos e aplicações ativos para conceder permissões.")
        else:
            st.markdown("**Aplicações por módulo**")
            for module_id, module_name in active_modules.items():
                apps_in_module = grouped_apps.get(module_id, [])
                if not apps_in_module:
                    continue
                st.markdown(f"*{module_name}*")
                cols = st.columns(3)
                for idx, app in enumerate(apps_in_module):
                    col = cols[idx % 3]
                    checked = col.checkbox(
                        app["name"],
                        key=f"perm_app_{module_id}_{app['id']}",
                        value=False,
                    )
                    if checked:
                        selected_app_ids.append(app["id"])

        submitted = st.form_submit_button("Vincular permissão")

    if not submitted:
        return

    user_id = user_options[user_name]
    user_role = user_lookup.get(user_name, {}).get("role", "USER")

    if user_role == "ADMIN":
        st.info("Usuário ADMIN já possui acesso total. Nenhuma permissão específica foi criada.")
        return

    if not selected_app_ids:
        st.error("Selecione ao menos uma aplicação.")
        return

    errors: list[str] = []
    infos: list[str] = []
    for app_id in selected_app_ids:
        try:
            app_lookup = next((a for a in apps_data if a["id"] == app_id), None)
            if not app_lookup:
                continue
            info = run_async(
                create_permission(user_id=user_id, module_id=app_lookup["module_id"], application_id=app_id)
            )
            if info:
                infos.append(info)
        except Exception as exc:
            errors.append(str(exc))

    if errors and not infos:
        st.error("Erro ao salvar permissão: " + "; ".join(errors))
    else:
        if infos:
            st.info(" / ".join(infos))
        st.success("Permissões vinculadas com sucesso.")
        st.rerun()


def _render_permission_list(
    users_data: list[dict], modules_data: list[dict], apps_data: list[dict]
) -> None:
    st.subheader("Permissões cadastradas")
    perm_data = run_async(list_permissions())
    if not perm_data:
        st.info("Nenhuma permissão cadastrada ainda.")
        return

    user_lookup = {u["id"]: u for u in users_data}
    module_lookup = {m["id"]: m for m in modules_data}
    app_lookup = {a["id"]: a for a in apps_data}

    header_cols = st.columns([2, 2.5, 2.5])
    header_cols[0].markdown("**Usuário**")
    header_cols[1].markdown("**Módulo**")
    header_cols[2].markdown("**Aplicação**")

    for perm in perm_data:
        cols = st.columns([2, 2.5, 2.5])
        cols[0].write(user_lookup.get(perm["user_id"], {}).get("username", "-"))
        cols[1].write(module_lookup.get(perm["module_id"], {}).get("name", "-"))
        cols[2].write(app_lookup.get(perm["application_id"], {}).get("name", "-"))
