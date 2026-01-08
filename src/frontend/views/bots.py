from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.agents import list_agents
from src.core.bots import (
    create_bot,
    delete_bot,
    ensure_tables,
    list_bot_agent_counts,
    list_bot_agents,
    list_bots,
    replace_bot_agents,
    update_bot,
)
from src.frontend.shared import page_header, render_db_status, run_async


def render() -> None:
    page_header("Bots", "Cadastre bots e vincule os agentes usados no atendimento.")
    render_db_status()
    run_async(ensure_tables())

    if "bots_selected_id" not in st.session_state:
        st.session_state.bots_selected_id = None
    if "bots_delete_id" not in st.session_state:
        st.session_state.bots_delete_id = None

    bots_data = run_async(list_bots())
    agents_data = run_async(list_agents())
    agent_counts = run_async(list_bot_agent_counts())

    selected = None
    selected_links: list[dict[str, Any]] = []
    if st.session_state.bots_selected_id is not None:
        selected = next(
            (b for b in bots_data if b["id"] == st.session_state.bots_selected_id),
            None,
        )
        if selected is None:
            st.session_state.bots_selected_id = None
        else:
            selected_links = run_async(list_bot_agents(selected["id"]))

    _render_bot_form(selected, agents_data, selected_links)
    st.divider()
    _render_bot_list(bots_data, agent_counts)


def _agent_option_label(agent: dict[str, Any]) -> str:
    status = "Ativo" if agent.get("ativo") else "Inativo"
    versao = agent.get("versao") or "-"
    return f"{agent.get('nome', '-')} - v{versao} ({status})"


def _build_agent_options(agents_data: list[dict[str, Any]]) -> tuple[dict[str, int], list[str]]:
    options: dict[str, int] = {}
    for agent in agents_data:
        label = _agent_option_label(agent)
        if label in options:
            label = f"{label} [ID {agent.get('id')}]"
        options[label] = int(agent.get("id"))
    return options, list(options.keys())


def _render_bot_form(
    selected: dict | None,
    agents_data: list[dict[str, Any]],
    selected_links: list[dict[str, Any]],
) -> None:
    is_edit = selected is not None
    st.subheader("Cadastro de bot" if not is_edit else "Editar bot")
    st.caption("Selecione o agente orquestrador e os agentes que o bot usara no atendimento.")

    active_agents = [a for a in agents_data if a.get("ativo")]
    if not active_agents:
        st.warning("Cadastre ao menos um agente em Agentes de IA antes de vincular.")
        return

    orchestrator_candidates = [
        a for a in active_agents if a.get("agente_orquestrador")
    ]
    if not orchestrator_candidates:
        st.warning("Marque ao menos um agente como orquestrador na tela de Agentes.")
        return

    agent_options, agent_labels = _build_agent_options(active_agents)
    orchestrator_options, orchestrator_labels = _build_agent_options(orchestrator_candidates)
    selected_agent_ids = {link["agent_id"] for link in selected_links}
    selected_orchestrator = next(
        (link["agent_id"] for link in selected_links if link.get("role") == "orquestrador"),
        None,
    )
    if is_edit and selected_orchestrator is not None:
        orchestrator_ids = set(orchestrator_options.values())
        if selected_orchestrator not in orchestrator_ids:
            st.warning(
                "O agente orquestrador atual nao esta elegivel. "
                "Selecione um novo agente orquestrador."
            )

    form_key_prefix = f"bot_{selected['id']}" if is_edit else "bot_new"
    with st.form("bot_form"):
        nome = st.text_input("Nome do bot *", value=selected["nome"] if is_edit else "")
        descricao = st.text_area(
            "Descricao",
            value=selected.get("descricao", "") if is_edit else "",
            height=90,
        )
        current_version = selected.get("versao", 1) if is_edit else 1
        version_default = current_version + 1 if is_edit else 1
        version_help = "Informe um numero inteiro."
        if is_edit:
            version_help = f"Versao atual: {current_version}. Informe uma versao maior para atualizar."
        versao = st.number_input(
            "Versao do bot *",
            min_value=1,
            step=1,
            value=int(version_default),
            help=version_help,
        )
        ativo = st.checkbox("Ativo", value=selected.get("ativo", True) if is_edit else True)

        default_orchestrator_index = 0
        if selected_orchestrator is not None:
            for idx, label in enumerate(orchestrator_labels):
                if orchestrator_options[label] == selected_orchestrator:
                    default_orchestrator_index = idx
                    break
        orchestrator_label = st.selectbox(
            "Agente orquestrador *",
            orchestrator_labels,
            index=default_orchestrator_index,
            key=f"{form_key_prefix}_orchestrator",
        )

        st.markdown("**Agentes vinculados**")
        selected_agent_ids_input: list[int] = []
        for label in agent_labels:
            agent_id = agent_options[label]
            checked = agent_id in selected_agent_ids
            if st.checkbox(label, value=checked, key=f"{form_key_prefix}_agent_{agent_id}"):
                selected_agent_ids_input.append(agent_id)

        submitted = st.form_submit_button("Atualizar bot" if is_edit else "Cadastrar bot")

    if not submitted:
        return

    if not nome.strip():
        st.error("Informe o nome do bot.")
        return

    try:
        orchestrator_id = orchestrator_options.get(orchestrator_label)
        if orchestrator_id is None:
            st.error("Selecione um agente orquestrador.")
            return

        if is_edit:
            run_async(
                update_bot(
                    selected["id"],
                    nome=nome,
                    descricao=descricao,
                    versao=versao,
                    ativo=ativo,
                )
            )
            bot_id = selected["id"]
        else:
            bot_id = run_async(
                create_bot(
                    nome=nome,
                    descricao=descricao,
                    versao=versao,
                    ativo=ativo,
                )
            )
        run_async(replace_bot_agents(bot_id, selected_agent_ids_input, orchestrator_id))
        st.success("Bot salvo com sucesso.")
        st.session_state.bots_selected_id = None
        st.rerun()
    except Exception as exc:
        st.error(f"Erro ao salvar bot: {exc}")


def _render_bot_list(bots_data: list[dict[str, Any]], agent_counts: dict[int, int]) -> None:
    st.subheader("Bots cadastrados")
    if not bots_data:
        st.info("Nenhum bot cadastrado ainda.")
        return

    header_cols = st.columns([2.3, 0.9, 2.4, 1.1, 1.4, 1.6])
    header_cols[0].markdown("**Bot**")
    header_cols[1].markdown("**Versao**")
    header_cols[2].markdown("**Descricao**")
    header_cols[3].markdown("**Agentes**")
    header_cols[4].markdown("**Status**")
    header_cols[5].markdown("**Acoes**")

    for bot in bots_data:
        cols = st.columns([2.3, 0.9, 2.4, 1.1, 1.4, 1.6])
        cols[0].write(bot.get("nome") or "-")
        cols[1].write(bot.get("versao") or "-")
        cols[2].write(bot.get("descricao") or "-")
        cols[3].write(agent_counts.get(bot["id"], 0))
        status = "Ativo" if bot.get("ativo") else "Inativo"
        cols[4].write(status)
        edit_key = f"edit_bot_{bot['id']}"
        if cols[5].button("Editar", key=edit_key, use_container_width=True):
            st.session_state.bots_selected_id = bot["id"]
            st.rerun()
        delete_key = f"delete_bot_{bot['id']}"
        if cols[5].button("Excluir", key=delete_key, type="secondary", use_container_width=True):
            st.session_state.bots_delete_id = bot["id"]
            st.session_state.bots_selected_id = None
            st.rerun()

    if st.session_state.bots_selected_id is not None:
        if st.button("Cancelar edicao", type="secondary"):
            st.session_state.bots_selected_id = None
            st.rerun()

    if st.session_state.bots_delete_id is not None:
        bot_to_delete = next(
            (b for b in bots_data if b["id"] == st.session_state.bots_delete_id),
            None,
        )
        if bot_to_delete is None:
            st.session_state.bots_delete_id = None
            return
        st.warning(f"Confirma a exclusao do bot '{bot_to_delete.get('nome', '-')}'?")
        confirm_cols = st.columns([1, 1])
        if confirm_cols[0].button("Confirmar exclusao", use_container_width=True):
            try:
                run_async(delete_bot(bot_to_delete["id"]))
                st.success("Bot excluido com sucesso.")
                st.session_state.bots_delete_id = None
                st.rerun()
            except Exception as exc:
                st.error(f"Erro ao excluir bot: {exc}")
        if confirm_cols[1].button("Cancelar", use_container_width=True):
            st.session_state.bots_delete_id = None
            st.rerun()
