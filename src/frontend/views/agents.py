from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.agent_architecture import AGENT_DISPLAY_NAMES, AgentRole, resolve_role_label
from src.core.agents import (
    create_agent,
    delete_agent,
    ensure_default_agents,
    ensure_tables,
    list_agents,
    update_agent,
)
from src.core.ia_settings import ensure_tables as ensure_ia_tables
from src.core.ia_settings import list_models
from src.core.rag_management import (
    RAG_PROVIDER_CHROMADB,
    RAG_PROVIDER_OPENAI,
    list_rags,
)
from src.frontend.shared import page_header, render_db_status, run_async

PROVIDER_LABELS = {
    RAG_PROVIDER_OPENAI: "OpenAI",
    RAG_PROVIDER_CHROMADB: "ChromaDB",
}


def render() -> None:
    page_header("Agentes", "Cadastre e gerencie agentes de IA.")
    render_db_status()
    run_async(ensure_tables())

    if "agents_selected_id" not in st.session_state:
        st.session_state.agents_selected_id = None
    if "agents_delete_id" not in st.session_state:
        st.session_state.agents_delete_id = None

    rags_data = run_async(list_rags())
    run_async(ensure_ia_tables())
    models_data = run_async(list_models(include_inactive=True))
    active_models = [m for m in models_data if m.get("is_active")]
    if active_models:
        run_async(ensure_default_agents(active_models[0]["name"]))
    agents_data = run_async(list_agents())

    selected = None
    if st.session_state.agents_selected_id is not None:
        selected = next(
            (a for a in agents_data if a["id"] == st.session_state.agents_selected_id),
            None,
        )
        if selected is None:
            st.session_state.agents_selected_id = None

    _render_agent_form(selected, rags_data, models_data)
    st.divider()
    _render_agent_list(agents_data)


def _rag_option_label(rag: dict[str, Any]) -> str:
    provider = PROVIDER_LABELS.get(rag.get("provedor_rag"), rag.get("provedor_rag") or "-")
    status = "Ativo" if rag.get("ativo") else "Inativo"
    return f"{rag.get('nome', '-')} • {provider} ({status})"


def _build_model_options(models_data: list[dict[str, Any]]) -> tuple[dict[str, str], list[str]]:
    model_options: dict[str, str] = {}
    for model in models_data:
        status = "Ativo" if model.get("is_active") else "Inativo"
        label = f"{model.get('provider_name', '-')} • {model.get('name', '-')} ({status})"
        if label in model_options:
            label = f"{label} [ID {model.get('id')}]"
        model_options[label] = model.get("name", "")
    return model_options, list(model_options.keys())


def _build_role_options() -> tuple[dict[str, str], list[str]]:
    options: dict[str, str] = {"Selecione o papel": ""}
    for role in AgentRole:
        label = AGENT_DISPLAY_NAMES.get(role, role.value)
        options[label] = role.value
    return options, list(options.keys())


def _format_role_label(value: str | None) -> str:
    role = resolve_role_label(value)
    if role:
        return AGENT_DISPLAY_NAMES.get(role, role.value)
    return value or "-"


def _render_agent_form(
    selected: dict | None,
    rags_data: list[dict[str, Any]],
    models_data: list[dict[str, Any]],
) -> None:
    is_edit = selected is not None
    st.subheader("Cadastro de agente" if not is_edit else "Editar agente")
    st.caption("Campos com * são obrigatórios.")

    rag_options = {"Sem RAG": None}
    for rag in rags_data:
        rag_options[_rag_option_label(rag)] = rag["id"]

    option_labels = list(rag_options.keys())
    selected_rag_id = selected.get("rag_id") if is_edit else None
    default_index = 0
    if selected_rag_id is not None:
        for idx, label in enumerate(option_labels):
            if rag_options[label] == selected_rag_id:
                default_index = idx
                break

    active_models = [m for m in models_data if m.get("is_active")]
    if not active_models:
        st.warning("Cadastre ao menos um modelo ativo em Configurações de IA antes de criar agentes.")
        return

    model_options, model_labels = _build_model_options(models_data)
    role_options, role_labels = _build_role_options()
    selected_model = selected.get("model") if is_edit else None
    model_index = 0
    if selected_model:
        for idx, label in enumerate(model_labels):
            if model_options[label] == selected_model:
                model_index = idx
                break
        else:
            model_labels.insert(0, f"{selected_model} (não cadastrado)")
            model_options[model_labels[0]] = selected_model
            model_index = 0

    selected_role = selected.get("papel") if is_edit else None
    role_index = 0
    if selected_role:
        for idx, label in enumerate(role_labels):
            if role_options[label] == selected_role:
                role_index = idx
                break

    current_version = selected.get("versao", 1) if is_edit else 1
    version_default = current_version + 1 if is_edit else 1
    version_help = "Informe um número inteiro."
    if is_edit:
        version_help = f"Versão atual: {current_version}. Informe uma versão maior para atualizar."

    with st.form("agent_form"):
        nome = st.text_input("Nome do agente *", value=selected["nome"] if is_edit else "")
        role_label = st.selectbox("Papel do agente *", role_labels, index=role_index)
        descricao = st.text_area(
            "Descrição",
            value=selected.get("descricao", "") if is_edit else "",
            height=90,
        )
        agente_orquestrador = st.checkbox(
            "Agente orquestrador",
            value=selected.get("agente_orquestrador", False) if is_edit else False,
        )
        system_prompt = st.text_area(
            "Prompt do agente *",
            value=selected.get("system_prompt", "") if is_edit else "",
            height=160,
        )
        versao = st.number_input(
            "Versão do agente *",
            min_value=1,
            step=1,
            value=int(version_default),
            help=version_help,
        )
        model_label = st.selectbox("Modelo *", model_labels, index=model_index)
        rag_label = st.selectbox("RAG associado", option_labels, index=default_index)
        ativo = st.checkbox("Ativo", value=selected.get("ativo", True) if is_edit else True)
        submitted = st.form_submit_button("Atualizar agente" if is_edit else "Cadastrar agente")

    if not submitted:
        return

    if not nome.strip():
        st.error("Informe o nome do agente.")
        return
    if not system_prompt.strip():
        st.error("Informe o prompt do agente.")
        return

    role_value = role_options.get(role_label, "").strip()
    if not role_value:
        st.error("Informe o papel do agente.")
        return

    model_value = model_options.get(model_label, "").strip()
    if not model_value:
        st.error("Informe o modelo do agente.")
        return

    rag_id = rag_options.get(rag_label)
    try:
        if is_edit:
            run_async(
                update_agent(
                    selected["id"],
                    nome=nome,
                    papel=role_value,
                    descricao=descricao,
                    agente_orquestrador=agente_orquestrador,
                    system_prompt=system_prompt,
                    model=model_value,
                    versao=versao,
                    ativo=ativo,
                    rag_id=rag_id,
                )
            )
            st.success("Agente atualizado com sucesso.")
            st.session_state.agents_selected_id = None
        else:
            run_async(
                create_agent(
                    nome=nome,
                    papel=role_value,
                    descricao=descricao,
                    agente_orquestrador=agente_orquestrador,
                    system_prompt=system_prompt,
                    model=model_value,
                    versao=versao,
                    ativo=ativo,
                    rag_id=rag_id,
                )
            )
            st.success("Agente cadastrado com sucesso.")
        st.rerun()
    except Exception as exc:
        st.error(f"Erro ao salvar agente: {exc}")


def _render_agent_list(agents_data: list[dict[str, Any]]) -> None:
    st.subheader("Agentes cadastrados")
    if not agents_data:
        st.info("Nenhum agente cadastrado ainda.")
        return

    header_cols = st.columns([2.2, 1.4, 1.0, 2.5, 2.4, 1.2, 1.5])
    header_cols[0].markdown("**Agente**")
    header_cols[1].markdown("**Papel**")
    header_cols[2].markdown("**Versão**")
    header_cols[3].markdown("**Modelo**")
    header_cols[4].markdown("**RAG**")
    header_cols[5].markdown("**Status**")
    header_cols[6].markdown("**Ações**")

    for agent in agents_data:
        cols = st.columns([2.2, 1.4, 1.0, 2.5, 2.4, 1.2, 1.5])
        cols[0].write(agent.get("nome") or "-")
        cols[1].write(_format_role_label(agent.get("papel")))
        cols[2].write(agent.get("versao") or "-")
        cols[3].write(agent.get("model") or "-")
        rag_label = "-"
        if agent.get("rag_nome"):
            provider = PROVIDER_LABELS.get(agent.get("rag_provedor"), agent.get("rag_provedor") or "-")
            rag_label = f"{agent.get('rag_nome')} • {provider}"
        cols[4].write(rag_label)
        status = "Ativo" if agent.get("ativo") else "Inativo"
        status_icon = "🟢" if agent.get("ativo") else "⭕️"
        cols[5].write(f"{status_icon} {status}")
        edit_key = f"edit_agent_{agent['id']}"
        if cols[6].button("Editar", key=edit_key, use_container_width=True):
            st.session_state.agents_selected_id = agent["id"]
            st.rerun()
        delete_key = f"delete_agent_{agent['id']}"
        if cols[6].button("Excluir", key=delete_key, type="secondary", use_container_width=True):
            st.session_state.agents_delete_id = agent["id"]
            st.session_state.agents_selected_id = None
            st.rerun()

    if st.session_state.agents_selected_id is not None:
        if st.button("Cancelar edição", type="secondary"):
            st.session_state.agents_selected_id = None
            st.rerun()

    if st.session_state.agents_delete_id is not None:
        agent_to_delete = next(
            (a for a in agents_data if a["id"] == st.session_state.agents_delete_id),
            None,
        )
        if agent_to_delete is None:
            st.session_state.agents_delete_id = None
            return
        st.warning(f"Confirma a exclusão do agente '{agent_to_delete.get('nome', '-')}'?")
        confirm_cols = st.columns([1, 1])
        if confirm_cols[0].button("Confirmar exclusão", use_container_width=True):
            try:
                run_async(delete_agent(agent_to_delete["id"]))
                st.success("Agente excluído com sucesso.")
                st.session_state.agents_delete_id = None
                st.rerun()
            except Exception as exc:
                st.error(f"Erro ao excluir agente: {exc}")
        if confirm_cols[1].button("Cancelar", use_container_width=True):
            st.session_state.agents_delete_id = None
            st.rerun()
