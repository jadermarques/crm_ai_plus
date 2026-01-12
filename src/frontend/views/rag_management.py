from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Backend Logic
from src.core.rag_management import (
    RAG_PROVIDER_CHROMADB,
    RAG_PROVIDER_OPENAI,
    create_rag,
    delete_rag,
    ensure_tables,
    list_rags,
    update_rag,
)
from src.frontend.shared import page_header, render_db_status, run_async

# Provider Options
PROVIDER_OPTIONS = {
    RAG_PROVIDER_CHROMADB: "ChromaDB (Local/Server)",
    RAG_PROVIDER_OPENAI: "OpenAI Assistants (File Search)",
}


def render() -> None:
    page_header("Gerenciamento RAG", "Cadastre e gerencie suas coleções de conhecimento.")
    render_db_status()
    run_async(ensure_tables())

    if "rag_selected_id" not in st.session_state:
        st.session_state.rag_selected_id = None
    if "rag_delete_id" not in st.session_state:
        st.session_state.rag_delete_id = None

    # Load Data
    rags_data = run_async(list_rags())

    # Selection Logic
    selected = None
    if st.session_state.rag_selected_id is not None:
        selected = next((r for r in rags_data if r["id"] == st.session_state.rag_selected_id), None)
        if selected is None:
            st.session_state.rag_selected_id = None

    # Helper: Find index for provider selectbox
    selected_provider = selected.get("provedor_rag") if selected else RAG_PROVIDER_OPENAI
    provider_keys = list(PROVIDER_OPTIONS.keys())
    provider_labels = list(PROVIDER_OPTIONS.values())
    try:
        provider_index = provider_keys.index(selected_provider)
    except ValueError:
        provider_index = 0

    # --- Form ---
    is_edit = selected is not None
    st.subheader("Cadastro de Coleção" if not is_edit else "Editar Coleção")
    st.caption("Associe um ID de coleção (ex: Assistant ID ou Chroma Collection) a um nome amigável.")

    with st.form("rag_form"):
        col1, col2 = st.columns([1, 1])
        nome = col1.text_input("Nome Amigável *", value=selected["nome"] if is_edit else "", placeholder="Ex: Base Pneus 2025")
        provider_label = col2.selectbox("Provedor *", provider_labels, index=provider_index)
        
        rag_id = st.text_input(
            "ID da Coleção / Assistant ID *", 
            value=selected["rag_id"] if is_edit else "",
            placeholder="Ex: asst_abc123... ou 'pneus_collection'",
            help="Para OpenAI, use o ID do Assistant. Para ChromaDB, use o nome da coleção."
        )
        
        descricao = st.text_area("Descrição", value=selected.get("descricao", "") if is_edit else "", height=80)
        ativo = st.checkbox("Ativo", value=selected.get("ativo", True) if is_edit else True)
        
        submitted = st.form_submit_button("Salvar Coleção" if not is_edit else "Atualizar Coleção")

    if submitted:
        if not nome.strip():
            st.error("Informe um nome para a coleção.")
        elif not rag_id.strip():
            st.error("Informe o ID da coleção.")
        else:
            # Map label back to key
            provider_key = provider_keys[provider_labels.index(provider_label)]
            
            try:
                if is_edit:
                    run_async(update_rag(
                        selected["id"],
                        nome=nome,
                        rag_id=rag_id,
                        descricao=descricao,
                        ativo=ativo,
                        provedor_rag=provider_key
                    ))
                    st.success("Coleção atualizada com sucesso.")
                    st.session_state.rag_selected_id = None
                else:
                    run_async(create_rag(
                        nome=nome,
                        rag_id=rag_id,
                        descricao=descricao,
                        ativo=ativo,
                        provedor_rag=provider_key
                    ))
                    st.success("Coleção criada com sucesso.")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")

    # --- List ---
    st.divider()
    st.subheader("Coleções Cadastradas")
    
    if not rags_data:
        st.info("Nenhuma coleção cadastrada. Adicione uma acima.")
        return

    # Table Header
    cols = st.columns([2, 1.5, 2.5, 1, 1.5])
    cols[0].markdown("**Nome**")
    cols[1].markdown("**Provedor**")
    cols[2].markdown("**ID Técnico**")
    cols[3].markdown("**Status**")
    cols[4].markdown("**Ações**")

    for item in rags_data:
        cols = st.columns([2, 1.5, 2.5, 1, 1.5])
        cols[0].write(item["nome"])
        cols[1].write(PROVIDER_OPTIONS.get(item["provedor_rag"], item["provedor_rag"]))
        cols[2].code(item["rag_id"])
        
        status_icon = "🟢" if item["ativo"] else "🔴"
        cols[3].write(status_icon)
        
        if cols[4].button("Editar", key=f"edit_{item['id']}", use_container_width=True):
            st.session_state.rag_selected_id = item["id"]
            st.rerun()
            
        if cols[4].button("Excluir", key=f"del_{item['id']}", type="secondary", use_container_width=True):
            st.session_state.rag_delete_id = item["id"]
            st.session_state.rag_selected_id = None
            st.rerun()

    # --- Delete Confirmation ---
    if st.session_state.rag_delete_id is not None:
        to_delete = next((r for r in rags_data if r["id"] == st.session_state.rag_delete_id), None)
        if to_delete:
            st.warning(f"Tem certeza que deseja excluir a coleção '{to_delete['nome']}'?")
            c1, c2 = st.columns([1,1])
            if c1.button("Confirmar Exclusão", type="primary", use_container_width=True):
                try:
                    run_async(delete_rag(to_delete["id"]))
                    st.success("Removido com sucesso.")
                    st.session_state.rag_delete_id = None
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao excluir: {e}")
            
            if c2.button("Cancelar", use_container_width=True):
                st.session_state.rag_delete_id = None
                st.rerun()
