from __future__ import annotations

import httpx
import streamlit as st

from src.core.chatwoot_params import get_params
from src.frontend.shared import page_header, render_db_status, run_async


def render() -> None:
    page_header("Conexão Chatwoot")
    render_db_status()

    params = run_async(get_params())
    if not params:
        st.warning(
            "Parâmetros do Chatwoot não configurados. Cadastre em Gestão > Parâmetros Chatwoot."
        )
        return

    base_url = (params.get("chatwoot_url") or "").rstrip("/")
    token = params.get("chatwoot_api_token") or ""
    account_id = params.get("chatwoot_account_id")
    version = params.get("chatwoot_version") or ""

    st.info(
        f"Base URL: {base_url or 'não definida'} | Account ID: {account_id or '-'} | Versão: {version or '-'}"
    )

    status_card = st.container()

    def check_connection() -> None:
        if not (base_url and token and account_id):
            st.error("Parâmetros incompletos. Ajuste em Parâmetros Chatwoot.")
            return

        endpoint = f"{base_url}/api/v1/accounts/{account_id}/agents"
        headers = {"api_access_token": token}
        try:
            with httpx.Client(timeout=httpx.Timeout(5.0, read=8.0)) as client:
                resp = client.get(endpoint, headers=headers)
        except httpx.HTTPError as exc:
            st.error(f"Falha na requisição: {exc}")
            return

        if not resp.is_success:
            st.error(f"Chatwoot indisponível (status {resp.status_code}).")
            return

        try:
            data = resp.json()
        except ValueError:
            st.error("Resposta inválida do Chatwoot (não é JSON).")
            return
        if isinstance(data, list):
            agents = data
        else:
            agents = data.get("agents") or data.get("data") or []
        online = sum(1 for a in agents if a.get("availability_status") == "online")
        total = len(agents)

        with status_card:
            st.success(
                f"Conectado ao Chatwoot. Usuários online: {online}/{total}",
                icon="✅",
            )
            st.caption(f"Endpoint verificado: {endpoint}")

    if st.button("Verificar conexão", type="primary"):
        check_connection()
