# Changelog de Alterações - CRM AI Plus

Este arquivo registra automaticamente todas as alterações realizadas no projeto.

---

## 2026-01-12 às 00:33
**Prompt:** Adicionar instruções de serviço systemd para frontend e gestão

    **Modelo:** Claude (claude-sonnet-4-20250514)

    **Tempo de Execução:** ~2 minutos

    **Arquivos Alterados:**
        - MODIFICADO `src/frontend/views/int_chatwoot_meta.py`

    **Resumo das Alterações:**
        Expandido guia de configuração na UI para incluir instruções de criação de serviço systemd para o frontend (Streamlit) e uma tabela de comandos para gerenciamento (status, restart, stop, logs) de ambos os serviços.

---

## 2026-01-12 às 00:20
**Prompt:** Configurar serviço persistente e remover logs de debug

    **Modelo:** Claude (claude-sonnet-4-20250514)

    **Tempo de Execução:** ~2 minutos

    **Arquivos Alterados:**
        - MODIFICADO `src/backend/api/webhooks.py`
        - MODIFICADO `src/frontend/views/int_chatwoot_meta.py`

    **Resumo das Alterações:**
        Removidos logs de debug temporários do webhook após validação. Adicionada seção na documentação da UI ("Manter o Serviço Rodando") com instruções passo-a-passo para criar um serviço systemd e manter o backend ativo em segundo plano.

---

## 2026-01-12 às 00:16
**Prompt:** Corrigir erro ValueError no httpx.Timeout

    **Modelo:** Claude (claude-sonnet-4-20250514)

    **Tempo de Execução:** < 1 minuto

    **Arquivos Alterados:**
        - MODIFICADO `src/backend/api/webhooks.py`

    **Resumo das Alterações:**
        Corrigida a inicialização do objeto `httpx.Timeout` que causava erro 500. Foi definido um timeout padrão de 15.0s junto com especificações de connect e read.

---

## 2026-01-12 às 00:14
**Prompt:** Atualizar instruções de execução do backend para conexões externas

    **Modelo:** Claude (claude-sonnet-4-20250514)

    **Tempo de Execução:** < 1 minuto

    **Arquivos Alterados:**
        - MODIFICADO `src/frontend/views/int_chatwoot_meta.py`

    **Resumo das Alterações:**
        Atualizado o guia de configuração na UI para incluir o parâmetro `--host 0.0.0.0` no comando do uvicorn, necessário para receber webhooks de IPs externos.

---

## 2026-01-12 às 00:10
**Prompt:** Adicionar logs de debug no terminal para o webhook Chatwoot-Meta

    **Modelo:** Claude (claude-sonnet-4-20250514)

    **Tempo de Execução:** ~2 minutos

    **Arquivos Alterados:**
        - MODIFICADO `src/backend/api/webhooks.py`

    **Resumo das Alterações:**
        Inseridos prints de debug (`[DEBUG] ...`) no endpoint `chatwoot_meta_webhook` para permitir visualização direta no terminal do uvicorn sobre payload recebido, eventos ignorados e status de atualização.

---

## 2026-01-11 às 23:36
**Prompt:** Adicionar campo webhook_path configurável e renomear aplicações de integração

    **Modelo:** Claude (claude-sonnet-4-20250514)

    **Tempo de Execução:** ~5 minutos

    **Arquivos Alterados:**
        - MODIFICADO `src/frontend/config/ui_structure.py`
        - MODIFICADO `src/core/management.py`
        - MODIFICADO `src/core/integration_chatwoot_meta.py`
        - MODIFICADO `src/frontend/views/int_chatwoot_meta.py`
        - MODIFICADO `src/frontend/views/int_chatwoot_google.py`

    **Resumo das Alterações:**
        Renomeadas aplicações no menu: "Int. Chatwoot-Meta" → "Int. Meta", "Int. Chatwoot - Google" → "Int. Google Ads". Adicionado campo configurável `webhook_path` na tabela de configuração, formulário e aba Webhook para permitir personalização do path do endpoint.

---

## 2026-01-11 às 23:33
**Prompt:** Ajustar formato do changelog para usar indentação

    **Modelo:** Claude (claude-sonnet-4-20250514)

    **Tempo de Execução:** ~1 minuto

    **Arquivos Alterados:**
        - MODIFICADO `.agent/changelog.md`
        - MODIFICADO `.agent/workflows/changelog.md`

    **Resumo das Alterações:**
        Atualizado formato do changelog para usar indentação, facilitando a identificação visual entre o prompt e seus detalhes.

---

## 2026-01-11 às 23:29
**Prompt:** Criar sistema de registro de alterações (changelog)

    **Modelo:** Claude (claude-sonnet-4-20250514)

    **Tempo de Execução:** ~2 minutos

    **Arquivos Alterados:**
        - CRIADO `.agent/workflows/changelog.md`
        - CRIADO `.agent/changelog.md`

    **Resumo das Alterações:**
        Criada regra persistente para registro automático de alterações e arquivo de log inicial.

---

## 2026-01-11 às 23:29
**Prompt:** Corrigir warning de complexidade cognitiva em int_chatwoot_meta.py

    **Modelo:** Claude (claude-sonnet-4-20250514)

    **Tempo de Execução:** ~2 minutos

    **Arquivos Alterados:**
        - MODIFICADO `src/frontend/views/int_chatwoot_meta.py`

    **Resumo das Alterações:**
        Extraída lógica de validação para funções auxiliares `_get_config_defaults` e `_handle_config_submit` para reduzir complexidade cognitiva de 16 para <15.

---

## 2026-01-11 às 23:25
**Prompt:** Adicionar campo para URL externa do webhook na integração Chatwoot-Meta

    **Modelo:** Claude (claude-sonnet-4-20250514)

    **Tempo de Execução:** ~5 minutos

    **Arquivos Alterados:**
        - MODIFICADO `src/core/integration_chatwoot_meta.py`
        - MODIFICADO `src/frontend/views/int_chatwoot_meta.py`

    **Resumo das Alterações:**
        Adicionada coluna `webhook_external_url` na tabela de configuração, campo no formulário de configurações e exibição da URL externa na aba Webhook. Adicionada migração automática para criar a coluna.

---

## 2026-01-11 às 23:12
**Prompt:** Documentar código em português e criar regra persistente de documentação

    **Modelo:** Claude (claude-sonnet-4-20250514)

    **Tempo de Execução:** ~20 minutos

    **Arquivos Alterados:**
        - CRIADO `.agent/workflows/documentacao.md`
        - MODIFICADO `src/core/integration_chatwoot_meta.py`
        - MODIFICADO `src/frontend/views/int_chatwoot_meta.py`
        - MODIFICADO `src/frontend/views/int_chatwoot_google.py`
        - MODIFICADO `src/backend/api/webhooks.py`
        - MODIFICADO `src/core/management.py`
        - MODIFICADO `src/frontend/app.py`
        - MODIFICADO `src/core/config.py`
        - MODIFICADO `src/core/database.py`
        - MODIFICADO `src/core/auth.py`

    **Resumo das Alterações:**
        Convertidas todas as docstrings para português do Brasil (Google-style). Criada regra persistente para documentação em português. Adicionado guia completo de configuração na view Int. Chatwoot-Meta.

---
