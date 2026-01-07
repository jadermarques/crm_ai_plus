from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.ia_settings import (
    create_model,
    create_provider,
    ensure_tables,
    list_models,
    list_providers,
    update_model,
    update_provider,
)
from src.frontend.shared import page_header, render_db_status, run_async


def _format_cost(value: float | None) -> str:
    if value is None:
        return "-"
    return f"US$ {value:,.3f} / 1 milhão de tokens"


def render() -> None:
    page_header("Configurações de IA", "Gerencie provedores e modelos.")
    render_db_status()
    run_async(ensure_tables())

    providers_tab, models_tab = st.tabs(["Provedores", "Modelos"])

    with providers_tab:
        _render_providers()
    with models_tab:
        _render_models()


def _render_providers() -> None:
    if "ia_providers_selected_id" not in st.session_state:
        st.session_state.ia_providers_selected_id = None

    providers_data = run_async(list_providers())
    selected = None
    if st.session_state.ia_providers_selected_id is not None:
        selected = next(
            (p for p in providers_data if p["id"] == st.session_state.ia_providers_selected_id),
            None,
        )
        if selected is None:
            st.session_state.ia_providers_selected_id = None

    st.subheader("Provedores")
    with st.form("provider_form"):
        name = st.text_input("Provedor", value=selected["name"] if selected else "")
        is_active = st.checkbox(
            "Ativo",
            value=selected.get("is_active", True) if selected else True,
            help="Marque para deixar o provedor disponível.",
        )
        submitted = st.form_submit_button("Atualizar provedor" if selected else "Criar provedor")

    if submitted:
        if not name.strip():
            st.error("Informe o nome do provedor.")
        else:
            try:
                if selected:
                    run_async(update_provider(selected["id"], name=name, is_active=is_active))
                    st.success("Provedor atualizado com sucesso.")
                    st.session_state.ia_providers_selected_id = None
                else:
                    run_async(create_provider(name=name, is_active=is_active))
                    st.success("Provedor criado com sucesso.")
                st.rerun()
            except Exception as exc:
                st.error(f"Erro ao salvar provedor: {exc}")

    st.caption("Selecione um provedor para editar ou crie um novo.")
    df = pd.DataFrame(providers_data)[["id", "name", "is_active"]] if providers_data else pd.DataFrame()
    if not df.empty:
        df.rename(columns={"id": "ID", "name": "Provedor", "is_active": "Ativo"}, inplace=True)
        st.dataframe(df, use_container_width=True, hide_index=True)
        selected_name = st.selectbox(
            "Selecionar provedor para edição",
            ["-"] + df["Provedor"].tolist(),
            index=0,
        )
        if selected_name != "-":
            selected_row = df[df["Provedor"] == selected_name].iloc[0]
            st.session_state.ia_providers_selected_id = int(selected_row["ID"])


def _render_models() -> None:
    if "ia_models_selected_id" not in st.session_state:
        st.session_state.ia_models_selected_id = None

    providers_data = run_async(list_providers(include_inactive=False))
    models_data = run_async(list_models())

    selected_model = None
    if st.session_state.ia_models_selected_id is not None:
        selected_model = next(
            (m for m in models_data if m["id"] == st.session_state.ia_models_selected_id),
            None,
        )
        if selected_model is None:
            st.session_state.ia_models_selected_id = None

    provider_options = {p["name"]: p["id"] for p in providers_data}
    if not provider_options:
        st.warning("Cadastre um provedor ativo para criar modelos.")
        return

    st.subheader("Modelos")
    with st.form("model_form"):
        model_name = st.text_input("Modelo", value=selected_model["name"] if selected_model else "")
        provider_name_default = (
            next((n for n, pid in provider_options.items() if pid == selected_model["provider_id"]), None)
            if selected_model
            else None
        )
        provider_name = st.selectbox(
            "Provedor",
            list(provider_options.keys()),
            index=list(provider_options.keys()).index(provider_name_default)
            if provider_name_default in provider_options
            else 0,
        )
        is_active = st.checkbox(
            "Ativo",
            value=selected_model.get("is_active", True) if selected_model else True,
            help="Marque para deixar o modelo disponível.",
        )
        cost_input = st.number_input(
            "Custo token entrada (US$ / 1 milhão de tokens)",
            min_value=0.0,
            step=0.001,
            format="%.3f",
            value=float(selected_model["cost_input"]) if selected_model and selected_model["cost_input"] else 0.0,
        )
        cost_output = st.number_input(
            "Custo token saída (US$ / 1 milhão de tokens)",
            min_value=0.0,
            step=0.001,
            format="%.3f",
            value=float(selected_model["cost_output"]) if selected_model and selected_model["cost_output"] else 0.0,
        )
        col_submit, col_update = st.columns([1, 1])
        submitted = col_submit.form_submit_button("Atualizar modelo" if selected_model else "Criar modelo")
        update_prices = col_update.form_submit_button("Atualizar valores")

    if update_prices:
        st.info(
            "Busca automática de preços não implementada. Consulte o provedor e atualize os campos de custo manualmente.",
            icon="ℹ️",
        )

    if submitted:
        provider_id = provider_options.get(provider_name)
        if not model_name.strip():
            st.error("Informe o nome do modelo.")
        elif provider_id is None:
            st.error("Selecione um provedor.")
        else:
            try:
                if selected_model:
                    run_async(
                        update_model(
                            selected_model["id"],
                            provider_id=provider_id,
                            name=model_name,
                            is_active=is_active,
                            cost_input=cost_input,
                            cost_output=cost_output,
                        )
                    )
                    st.success("Modelo atualizado com sucesso.")
                    st.session_state.ia_models_selected_id = None
                else:
                    run_async(
                        create_model(
                            provider_id=provider_id,
                            name=model_name,
                            is_active=is_active,
                            cost_input=cost_input,
                            cost_output=cost_output,
                        )
                    )
                    st.success("Modelo criado com sucesso.")
                st.rerun()
            except Exception as exc:
                st.error(f"Erro ao salvar modelo: {exc}")

    st.caption("Selecione um modelo para editar ou crie um novo.")
    if models_data:
        df = pd.DataFrame(models_data)[
            ["id", "provider_name", "name", "cost_input", "cost_output", "is_active"]
        ]
        df.rename(
            columns={
                "id": "ID",
                "provider_name": "Provedor",
                "name": "Modelo",
                "cost_input": "Custo entrada",
                "cost_output": "Custo saída",
                "is_active": "Ativo",
            },
            inplace=True,
        )
        df["Custo entrada"] = df["Custo entrada"].apply(
            lambda v: _format_cost(float(v)) if v is not None else "-"
        )
        df["Custo saída"] = df["Custo saída"].apply(
            lambda v: _format_cost(float(v)) if v is not None else "-"
        )
        st.dataframe(df, use_container_width=True, hide_index=True)
        select_label = st.selectbox(
            "Selecionar modelo para edição",
            ["-"] + df["Modelo"].tolist(),
            index=0,
        )
        if select_label != "-":
            selected_row = df[df["Modelo"] == select_label].iloc[0]
            st.session_state.ia_models_selected_id = int(selected_row["ID"])
    else:
        st.info("Nenhum modelo cadastrado ainda.")
