from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.management import create_module, ensure_management_tables, list_modules, update_module
from src.frontend.shared import page_header, render_db_status, run_async


def render() -> None:
    page_header("Módulos", "Gerencie os módulos do sistema.")
    render_db_status()
    run_async(ensure_management_tables())

    if "modules_selected_id" not in st.session_state:
        st.session_state.modules_selected_id = None

    modules_data = run_async(list_modules())
    selected = None
    if st.session_state.modules_selected_id is not None:
        selected = next(
            (m for m in modules_data if m["id"] == st.session_state.modules_selected_id), None
        )
        if selected is None:
            st.session_state.modules_selected_id = None

    _render_module_form(selected)
    st.divider()
    _render_module_list(modules_data)


def _render_module_form(selected: dict | None) -> None:
    is_edit = selected is not None
    st.subheader("Cadastro de módulo" if not is_edit else "Editar módulo")
    with st.form("module_form"):
        name = st.text_input("Nome do módulo", value=selected["name"] if is_edit else "")
        description = st.text_area(
            "Descrição do módulo",
            value=selected.get("description", "") if is_edit else "",
            height=100,
        )
        is_active = st.checkbox(
            "Módulo ativo",
            value=selected.get("is_active", True) if is_edit else True,
            help="Desative para ocultar o módulo sem removê-lo.",
        )
        submitted = st.form_submit_button("Atualizar módulo" if is_edit else "Criar módulo")

    if not submitted:
        return

    if not name.strip():
        st.error("Informe o nome do módulo.")
        return

    try:
        if is_edit:
            run_async(
                update_module(
                    selected["id"],
                    name=name,
                    description=description,
                    is_active=is_active,
                )
            )
            st.success("Módulo atualizado com sucesso.")
            st.session_state.modules_selected_id = None
        else:
            run_async(create_module(name=name, description=description, is_active=is_active))
            st.success("Módulo criado com sucesso.")
        st.rerun()
    except Exception as exc:
        st.error(f"Erro ao salvar módulo: {exc}")


def _render_module_list(modules_data: list[dict]) -> None:
    st.subheader("Módulos cadastrados")
    if not modules_data:
        st.info("Nenhum módulo cadastrado ainda.")
        return

    header_cols = st.columns([3, 4, 2, 2])
    header_cols[0].markdown("**Nome**")
    header_cols[1].markdown("**Descrição**")
    header_cols[2].markdown("**Status**")
    header_cols[3].markdown("**Ações**")

    for module in modules_data:
        cols = st.columns([3, 4, 2, 2])
        cols[0].write(module.get("name") or "-")
        cols[1].write(module.get("description") or "-")
        status = "Ativo" if module.get("is_active", True) else "Desabilitado"
        status_icon = "🟢" if module.get("is_active", True) else "⭕️"
        cols[2].write(f"{status_icon} {status}")
        actions_col = cols[3]
        edit_key = f"edit_module_{module['id']}"
        if actions_col.button("Editar", key=edit_key, use_container_width=True):
            st.session_state.modules_selected_id = module["id"]
            st.rerun()

    if st.session_state.modules_selected_id is not None:
        if st.button("Cancelar edição", type="secondary"):
            st.session_state.modules_selected_id = None
            st.rerun()
