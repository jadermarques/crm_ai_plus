"""View da integração Int. Meta.

Este módulo fornece a interface Streamlit para configurar e gerenciar
a integração Chatwoot-Meta. Inclui abas para configurações e informações
do webhook.

Functions:
    render: Ponto de entrada principal para renderizar a view.
    _render_config_tab: Renderiza a aba de configurações.
    _render_webhook_tab: Renderiza a aba de informações do webhook.

Example:
    Este módulo é tipicamente chamado pelo roteador principal::

        from src.frontend.views import int_chatwoot_meta
        int_chatwoot_meta.render()
"""
from __future__ import annotations

import streamlit as st

from src.core.integration_chatwoot_meta import get_config, upsert_config
from src.frontend.shared import page_header, render_db_status, run_async

# Constantes para evitar duplicação de literais
_DEFAULT_WEBHOOK_PATH = "/api/v1/webhooks/chatwoot-meta"


def render() -> None:
    """Renderiza a view da integração Int. Meta.

    Ponto de entrada principal da view. Exibe o cabeçalho da página,
    status do banco de dados e duas abas: configuração e webhook.
    """
    page_header("Int. Meta")
    render_db_status()

    st.markdown("""
    Esta integração conecta o Chatwoot à Meta (WhatsApp/Facebook Ads).
    Quando uma mensagem chega via webhook do Chatwoot, o sistema identifica se veio de um anúncio
    e atualiza os atributos customizados da conversa.
    """)

    tab_config, tab_webhook = st.tabs(["⚙️ Configurações", "🔗 Webhook"])

    with tab_config:
        _render_config_tab()

    with tab_webhook:
        _render_webhook_tab()


def _get_config_defaults(config: dict | None) -> tuple[str, str, str, str, bool]:
    """Extrai valores padrão da configuração existente."""
    if not config:
        return "", "", "", _DEFAULT_WEBHOOK_PATH, True
    return (
        config.get("chatwoot_base_url", ""),
        config.get("chatwoot_api_token", ""),
        config.get("webhook_external_url", "") or "",
        config.get("webhook_path", "") or _DEFAULT_WEBHOOK_PATH,
        config.get("is_active", True),
    )


def _render_config_tab() -> None:
    """Renderiza a aba de configurações.

    Exibe um formulário para configurar a integração Chatwoot-Meta,
    incluindo campos para URL base, token da API, URL externa, path do webhook e status ativo.
    Gerencia o envio do formulário e persistência dos dados.
    """
    config = run_async(get_config())
    current_url, current_token, current_webhook_url, current_webhook_path, current_active = _get_config_defaults(config)

    with st.form("chatwoot_meta_config_form"):
        st.subheader("Configurações da Integração")

        chatwoot_url = st.text_input(
            "URL Base do Chatwoot",
            value=current_url,
            placeholder="https://app.chatwoot.com",
            help="URL base da sua instância Chatwoot (sem barra no final)",
        )

        chatwoot_token = st.text_input(
            "Token de API do Chatwoot",
            value=current_token,
            type="password",
            help="Token de acesso da API do Chatwoot",
        )

        st.divider()
        st.subheader("🌐 Configurações do Webhook")

        webhook_external_url = st.text_input(
            "URL Externa (IP ou Domínio)",
            value=current_webhook_url,
            placeholder="https://meusite.com.br ou http://123.45.67.89:8000",
            help="URL ou IP público onde o Chatwoot pode acessar o webhook. Se vazio, usará localhost.",
        )

        webhook_path = st.text_input(
            "Path do Endpoint",
            value=current_webhook_path,
            placeholder=_DEFAULT_WEBHOOK_PATH,
            help="Path do endpoint do webhook (deve começar com /)",
        )

        st.divider()

        is_active = st.checkbox(
            "Integração Ativa",
            value=current_active,
            help="Quando desativada, o webhook não processará as mensagens",
        )

        submitted = st.form_submit_button("Salvar Configurações", type="primary")

        if submitted:
            _handle_config_submit(chatwoot_url, chatwoot_token, webhook_external_url, webhook_path, is_active)

    if config:
        st.info(f"**Status:** {'✅ Ativa' if config.get('is_active') else '❌ Inativa'}")


def _handle_config_submit(chatwoot_url: str, chatwoot_token: str, webhook_url: str, webhook_path: str, is_active: bool) -> None:
    """Trata o envio do formulário de configuração."""
    if not chatwoot_url.strip():
        st.error("Informe a URL base do Chatwoot.")
        return
    if not chatwoot_token.strip():
        st.error("Informe o Token de API do Chatwoot.")
        return
    try:
        run_async(
            upsert_config(
                chatwoot_base_url=chatwoot_url.strip(),
                chatwoot_api_token=chatwoot_token.strip(),
                webhook_external_url=webhook_url.strip() or None,
                webhook_path=webhook_path.strip() or None,
                is_active=is_active,
            )
        )
        st.success("Configurações salvas com sucesso!")
        st.rerun()
    except Exception as exc:
        st.error(f"Erro ao salvar: {exc}")


def _render_webhook_tab() -> None:
    """Renderiza a aba de informações do webhook.

    Exibe a URL do webhook baseada na configuração salva, instruções de
    configuração para o Chatwoot e informações sobre os atributos customizados.
    Também mostra o status atual da integração.
    """
    config = run_async(get_config())

    st.subheader("Endpoint do Webhook")

    # Usa URL externa configurada ou fallback para localhost
    if config and config.get("webhook_external_url"):
        base_url = config["webhook_external_url"]
    else:
        import os
        host = os.getenv("WEBHOOK_HOST", "localhost")
        port = os.getenv("WEBHOOK_PORT", "8000")
        base_url = f"http://{host}:{port}"

    # Usa path configurado ou padrão
    webhook_path = config.get("webhook_path", _DEFAULT_WEBHOOK_PATH) if config else _DEFAULT_WEBHOOK_PATH
    webhook_url = f"{base_url}{webhook_path}"

    # Destaca se é URL externa ou localhost
    if config and config.get("webhook_external_url"):
        st.success("✅ URL Externa configurada:")
        st.code(webhook_url, language="text")
    else:
        st.warning("⚠️ URL usando localhost (configure a URL Externa na aba Configurações):")
        st.code(webhook_url, language="text")

    st.markdown("""
    ---
    ## 📋 Guia Completo de Configuração

    ### Pré-requisitos

    Antes de configurar a integração, certifique-se de que:

    1. **Servidor Backend rodando** - O servidor FastAPI deve estar em execução (aceitando conexões externas):
       ```bash
       python -m uvicorn src.backend.main:app --reload --host 0.0.0.0 --port 8000
       ```

    2. **Acesso ao Chatwoot** - Você precisa de acesso administrativo à sua instância Chatwoot

    3. **URL acessível** - O Chatwoot precisa conseguir acessar a URL do webhook.
       Para testes locais, use ferramentas como ngrok ou localtunnel.

    ---
    ### Passo 1: Configurar Credenciais neste Sistema

    1. Acesse a aba **"⚙️ Configurações"** acima
    2. Preencha a **URL Base do Chatwoot** (ex: `https://app.chatwoot.com`)
    3. Insira o **Token de API do Chatwoot** (obtido nas configurações do Chatwoot)
    4. Certifique-se de que **"Integração Ativa"** está marcado
    5. Clique em **"Salvar Configurações"**

    ---
    ### Passo 2: Obter Token de API no Chatwoot

    1. Acesse seu painel Chatwoot
    2. Vá em **Configurações** > **Perfil**
    3. Copie o **Access Token** da seção de API
    4. Cole o token na aba de Configurações deste sistema

    ---
    ### Passo 3: Configurar Webhook no Chatwoot

    1. No Chatwoot, vá em **Configurações** > **Integrações** > **Webhooks**
    2. Clique em **"Adicionar Novo Webhook"**
    3. Cole a URL do webhook mostrada acima
    4. Selecione os eventos:
       - ✅ `message_created` (obrigatório)
       - ✅ `conversation_created` (opcional)
    5. Clique em **"Criar Webhook"**

    ---
    ### Passo 4: Criar Atributos Customizados no Chatwoot

    Para que os dados sejam salvos corretamente, crie os seguintes atributos customizados:

    1. Vá em **Configurações** > **Atributos Customizados**
    2. Crie os seguintes atributos para **Conversas**:

    | Atributo | Tipo | Descrição |
    |----------|------|-----------|
    | `ad_headline` | Texto | Título do anúncio ou "Orgânico / Direto" |
    | `ad_source_id` | Texto | ID da fonte do anúncio ou "N/A" |
    | `ad_referral_type` | Lista | "ad" ou "organic" |

    ---
    ### Passo 5: Configurar Anúncios Click-to-WhatsApp no Meta

    Esta integração funciona automaticamente com anúncios **Click-to-WhatsApp** do Meta:

    3. Selecione **WhatsApp** como destino
    4. Certifique-se de que a **Integração de Rastreamento de Conversão** está ativa

    ---

    ### 🛠️ Manter o Serviço Rodando (Opcional - Recomendado)

    Para evitar que o backend pare ao fechar o terminal, configure um serviço systemd:

    1. Crie o arquivo de serviço:
       ```bash
       sudo nano /etc/systemd/system/crm-backend.service
       ```

    2. Cole o conteúdo (ajuste o usuário e caminho):
       ```ini
       [Unit]
       Description=CRM AI Plus Backend
       After=network.target

       [Service]
       User=jader
       WorkingDirectory=/home/jader/projects/crm_ai_plus
       ExecStart=/home/jader/projects/crm_ai_plus/venv/bin/python -m uvicorn src.backend.main:app --host 0.0.0.0 --port 8000
       Restart=always

       [Install]
       WantedBy=multi-user.target
       ```

    3. Ative e inicie o serviço:
       ```bash
       sudo systemctl enable crm-backend
       sudo systemctl start crm-backend
       ```

    4. Verifique o status:
       ```bash
       sudo systemctl status crm-backend
       ```

    ---

    ### 🖥️ Serviço para o Frontend (Streamlit)

    Para manter a interface gráfica rodando:

    1. Crie o arquivo de serviço:
       ```bash
       sudo nano /etc/systemd/system/crm-frontend.service
       ```

    2. Cole o conteúdo:
       ```ini
       [Unit]
       Description=CRM AI Plus Frontend
       After=network.target

       [Service]
       User=jader
       WorkingDirectory=/home/jader/projects/crm_ai_plus
       ExecStart=/home/jader/projects/crm_ai_plus/venv/bin/streamlit run src/frontend/app.py
       Restart=always

       [Install]
       WantedBy=multi-user.target
       ```

    3. Ative e inicie:
       ```bash
       sudo systemctl enable crm-frontend
       sudo systemctl start crm-frontend
       ```

    ---

    ### ⚙️ Gerenciamento dos Serviços

    Comandos úteis para pausar, reiniciar e verificar:

    | Ação | Backend (API) | Frontend (Interface) |
    |------|---------------|----------------------|
    | **Ver Status** | `sudo systemctl status crm-backend` | `sudo systemctl status crm-frontend` |
    | **Reiniciar** | `sudo systemctl restart crm-backend` | `sudo systemctl restart crm-frontend` |
    | **Parar** | `sudo systemctl stop crm-backend` | `sudo systemctl stop crm-frontend` |
    | **Ver Logs** | `journalctl -u crm-backend -f` | `journalctl -u crm-frontend -f` |
    4. O Meta enviará automaticamente dados de referral quando o usuário clicar no anúncio

    ---
    ### Verificação e Teste

    Após configurar tudo:

    1. Envie uma mensagem de teste pelo WhatsApp conectado ao Chatwoot
    2. Verifique os logs do servidor FastAPI
    3. Confirme que os atributos customizados foram atualizados na conversa

    ---
    ### Atributos Atualizados Automaticamente

    O webhook atualiza os seguintes atributos na conversa:

    | Atributo | Valor (se anúncio) | Valor (se orgânico) |
    |----------|-------------------|---------------------|
    | `ad_headline` | Título do anúncio | "Orgânico / Direto" |
    | `ad_source_id` | ID do anúncio | "N/A" |
    | `ad_referral_type` | "ad" | "organic" |

    ---
    ### Solução de Problemas

    **Webhook não está funcionando?**
    - Verifique se o servidor FastAPI está rodando
    - Confirme que a URL é acessível externamente (use ngrok para testes locais)
    - Verifique os logs do servidor para erros

    **Atributos não aparecem no Chatwoot?**
    - Certifique-se de que os atributos customizados foram criados com os nomes exatos
    - Verifique se o token de API tem permissões suficientes

    **Dados de anúncio não são capturados?**
    - Confirme que o anúncio é do tipo Click-to-WhatsApp
    - Verifique se o WhatsApp Business está configurado corretamente no Chatwoot
    """)

    config = run_async(get_config())
    if not config:
        st.warning("⚠️ Configure as credenciais na aba Configurações antes de usar o webhook.")
    elif not config.get("is_active"):
        st.warning("⚠️ A integração está desativada. Ative na aba Configurações.")
    else:
        st.success("✅ Integração configurada e ativa.")

