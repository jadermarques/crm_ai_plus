from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.management import (
    create_application,
    ensure_management_tables,
    list_applications,
    list_modules,
    update_application,
)
from src.frontend.shared import page_header, render_db_status, run_async


def render() -> None:
    page_header("Aplicações", "Cadastre e organize as aplicações por módulo.")
    render_db_status()
    run_async(ensure_management_tables())

    if "applications_selected_id" not in st.session_state:
        st.session_state.applications_selected_id = None

    modules_data = run_async(list_modules())
    apps_data = run_async(list_applications())

    selected = None
    if st.session_state.applications_selected_id is not None:
        selected = next(
            (a for a in apps_data if a["id"] == st.session_state.applications_selected_id),
            None,
        )
        if selected is None:
            st.session_state.applications_selected_id = None

    _render_application_form(selected, modules_data)
    st.divider()
    _render_application_list(apps_data)


def _render_application_form(selected: dict | None, modules_data: list[dict]) -> None:
    is_edit = selected is not None
    st.subheader("Cadastro de aplicação" if not is_edit else "Editar aplicação")
    module_options = {m["name"]: m["id"] for m in modules_data}
    if not module_options:
        st.warning("Cadastre um módulo antes de criar aplicações.")
        return

    default_module = (
        selected["module_id"] if is_edit else next(iter(module_options.values()))
    )
    module_names = list(module_options.keys())
    default_index = (
        module_names.index(next(k for k, v in module_options.items() if v == default_module))
        if default_module in module_options.values()
        else 0
    )

    with st.form("application_form"):
        name = st.text_input("Nome da aplicação", value=selected["name"] if is_edit else "")
        description = st.text_area(
            "Descrição da aplicação",
            value=selected.get("description", "") if is_edit else "",
            height=100,
        )
        module_name = st.selectbox("Módulo", module_names, index=default_index)
        is_active = st.checkbox(
            "Aplicação ativa",
            value=selected.get("is_active", True) if is_edit else True,
            help="Desative para ocultar a aplicação sem removê-la.",
        )
        submitted = st.form_submit_button("Atualizar aplicação" if is_edit else "Criar aplicação")

    if not submitted:
        return

    module_id = module_options.get(module_name)
    if not name.strip():
        st.error("Informe o nome da aplicação.")
        return
    if not module_id:
        st.error("Selecione um módulo.")
        return

    try:
        if is_edit:
            run_async(
                update_application(
                    selected["id"],
                    name=name,
                    description=description,
                    module_id=module_id,
                    is_active=is_active,
                )
            )
            st.success("Aplicação atualizada com sucesso.")
            st.session_state.applications_selected_id = None
        else:
            run_async(
                create_application(
                    name=name,
                    description=description,
                    module_id=module_id,
                    is_active=is_active,
                )
            )
            st.success("Aplicação criada com sucesso.")
        st.rerun()
    except Exception as exc:
        st.error(f"Erro ao salvar aplicação: {exc}")


def _render_application_list(apps_data: list[dict]) -> None:
    st.subheader("Aplicações cadastradas")
    if not apps_data:
        st.info("Nenhuma aplicação cadastrada ainda.")
        return

    header_cols = st.columns([2.5, 3, 2.5, 1.5, 2])
    header_cols[0].markdown("**Nome**")
    header_cols[1].markdown("**Descrição**")
    header_cols[2].markdown("**Módulo**")
    header_cols[3].markdown("**Status**")
    header_cols[4].markdown("**Ações**")

    for app in apps_data:
        cols = st.columns([2.5, 3, 2.5, 1.5, 2])
        cols[0].write(app.get("name") or "-")
        cols[1].write(app.get("description") or "-")
        cols[2].write(app.get("module_name") or "-")
        status = "Ativa" if app.get("is_active", True) else "Desabilitada"
        status_icon = "🟢" if app.get("is_active", True) else "⭕️"
        cols[3].write(f"{status_icon} {status}")
        actions_col = cols[4]
        edit_key = f"edit_app_{app['id']}"
        if actions_col.button("Editar", key=edit_key, use_container_width=True):
            st.session_state.applications_selected_id = app["id"]
            st.rerun()

    if st.session_state.applications_selected_id is not None:
        if st.button("Cancelar edição", type="secondary"):
            st.session_state.applications_selected_id = None
            st.rerun()
