from __future__ import annotations

import streamlit as st

from src.frontend.shared import page_header, render_db_status
from src.core.chatwoot_params import ensure_table, get_params, upsert_params
from src.frontend.shared import run_async


def render() -> None:
    page_header("Parâmetros Chatwoot")
    render_db_status()

    run_async(ensure_table())
    stored = run_async(get_params())

    if st.session_state.get("chatwoot_saved"):
        st.success("Parâmetros salvos com sucesso.")
        st.session_state["chatwoot_saved"] = False
    default_url = stored.get("chatwoot_url") if stored else ""
    default_token = stored.get("chatwoot_api_token") if stored else ""
    default_account_id = stored.get("chatwoot_account_id") if stored else 0
    default_version = stored.get("chatwoot_version") if stored else ""

    st.info("Esta aplicação mantém apenas um cadastro de parâmetros do Chatwoot.")

    with st.form("chatwoot_params_form"):
        chatwoot_url = st.text_input("CHATWOOT_URL", value=default_url)
        chatwoot_api_token = st.text_input(
            "CHATWOOT_API_TOKEN", value=default_token, type="password"
        )
        chatwoot_account_id = st.number_input(
            "CHATWOOT_ACCOUNT_ID", min_value=0, value=int(default_account_id)
        )
        chatwoot_version = st.text_input("CHATWOOT_VERSION", value=default_version)

        salvar = st.form_submit_button("SALVAR", type="primary", use_container_width=True)

    if salvar:
        if not (chatwoot_url and chatwoot_api_token and chatwoot_version):
            st.error("Todos os campos são obrigatórios.")
            return
        try:
            run_async(
                upsert_params(
                    chatwoot_url=chatwoot_url,
                    chatwoot_api_token=chatwoot_api_token,
                    chatwoot_account_id=int(chatwoot_account_id),
                    chatwoot_version=chatwoot_version,
                )
            )
            st.session_state["chatwoot_saved"] = True
            st.rerun()
        except Exception as exc:
            st.error(f"Erro ao salvar parâmetros: {exc}")
