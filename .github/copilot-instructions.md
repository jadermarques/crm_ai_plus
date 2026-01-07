# CRM AI Plus - Instruções para o Agente de Código

## Visão geral do projeto
- CRM com workspace em Streamlit, webhooks FastAPI para Chatwoot, Postgres como banco, Redis/Chroma/OpenAI para IA.
- Frontend: `src/frontend/app.py` usa navegação por módulos, autenticação com usuários no Postgres (hash PBKDF2) e páginas em `src/frontend/views/`.
- Backend: `src/backend/main.py` expõe webhooks; config/env via `src/core/config.py`; banco async via `src/core/database.py`.

## Convenções e padrões
- Preferir `async/await` para banco/HTTP; sessões via `get_sessionmaker()` e engine via `get_engine()` (um por loop).
- Configurações sempre por `get_settings()`; não hardcode segredos.
- Importar com caminho absoluto `src.`.
- Senhas: hash PBKDF2 (passlib) e mínimo de 6 caracteres.
- Não reformatar arquivos não tocados; comentários só se necessário para clareza.
- Usuário/login: usernames entre 3 e 20 caracteres, sempre em minúsculas (normalizar/validar na interface e backend).
- Entradas de contato: valide e-mails (`xxx@dominio.xxx` / `xxx@dominio.ccc.cc`) e telefones (`(xx)nnnnnnnnn` ou `+xx(nnnnnnnnn)`, 7–12 dígitos) sempre que solicitar ou persistir esses campos.
- Entradas de contato: valide e-mails (`xxx@dominio.xxx` / `xxx@dominio.ccc.cc`) e telefones (`(xx)nnnnnnnnn` ou `+xx(nnnnnnnnn)`, 7–12 dígitos) sempre que solicitar ou persistir esses campos.

## Fluxos principais
- Frontend: `streamlit run src/frontend/app.py` (requer `.env` e Postgres).
- Backend: `python -m uvicorn src.backend.main:app --reload --port 8000`.
- Criar/alterar usuário: `python -m src.scripts.create_user --username <user> [--update] [--password <senha>]`.

## Regras para o agente
- Ler estas instruções e `AGENTS.md` antes de editar.
- Não apagar instruções nem alterar comportamento de auth/banco sem necessidade.
- Todas as tabelas do banco devem ter `data_hora_inclusao` e `data_hora_alteracao` (`TIMESTAMPTZ`, defaults `now()`, trigger de atualização); use `ensure_audit_columns` ao criar novas tabelas.
- Manter português em mensagens exibidas ao usuário final.
- Evitar mudanças em arquivos fora do escopo solicitado.
- Ao adicionar nova lógica, preferir testes manuais simples (quando fizer sentido) e indicar no resumo.
- Sempre planejar e/ou adicionar testes unitários para novas regras de negócio; use `pytest`/`pytest-asyncio` em `tests/`.
- Se não for possível testar (ex.: UI pura), documentar o gap e sugerir testes manuais.
- Para mudanças em UI/Streamlit, sugerir e/ou adicionar teste E2E (ex.: Playwright/Selenium) quando viável; se não implementar, registrar plano/manual no resumo.
- Ao tocar fluxos de login/autenticação, atualizar ou criar testes cobrindo happy path e falhas (credenciais inválidas, usuário inexistente, senha mínima).
- Testes E2E devem rodar em modo headless e serem opt-in via `RUN_E2E=1` para não quebrar CI local; ao adicionar, documente dependências (playwright) e passos de setup.
- Inclua logs passo-a-passo nos testes (especialmente E2E) usando `logging` para facilitar depuração em tempo real (log_cli habilitado no pytest).
- Todos os projetos devem criar logs de teste por módulo (ex.: handler para `logs/tests/<arquivo>.log`), além do `log_cli` no terminal.
- Só execute testes se o usuário pedir explicitamente no prompt (ex.: terminar com “teste”/“faça testes”); caso contrário, planeje/descreva mas não execute. Se executar e falhar/for impossível, explique no resumo e liste como rodar.
- Sidebar do Streamlit: manter o estilo/estrutura atual (módulos expandíveis com subitens) e ícones; só alterar se solicitado explicitamente.
