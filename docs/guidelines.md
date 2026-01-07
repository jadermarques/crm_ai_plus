# Diretrizes de Desenvolvimento

## Setup
- Use Python 3.12, venv e `pip install -r requirements.txt`.
- Copie `.env.example` para `.env` e preencha `DATABASE_URL` (Postgres async), `REDIS_URL`, `OPENAI_API_KEY`, `CHROMA_HOST`.
- Parâmetros do Chatwoot são configurados via app (Gestão > Parâmetros Chatwoot) e armazenados no banco.

## Backend (FastAPI)
- Entrypoint: `src/backend/main.py`; webhooks em `src/backend/api/`.
- Sempre async; use `get_settings()` e `get_sessionmaker()`; nada de conexões manuais.
- Respostas JSON com códigos adequados; logar erros.

## Frontend (Streamlit)
- App em `src/frontend/app.py`; páginas em `src/frontend/views/`.
- Autenticação: usuários no Postgres com hash PBKDF2; mínimo 6 caracteres; criação/alteração via CLI `src/scripts/create_user.py`. Usernames 3–20 caracteres, sempre minúsculos (normalizar/validar). Tabela `users` inclui `full_name`, `email` (único), `role` (ADMIN/USER) e `is_active` (desabilitar em vez de excluir). Use `ensure_users_table`/`ensure_audit_columns` para manter colunas padrão.
- Mensagens ao usuário em português; mantenha navegação por módulos na sidebar.

## Banco e Config
- Helpers em `src/core/database.py` (engine por loop) e `src/core/config.py` (Pydantic Settings).
- Não hardcode segredos; tudo via `.env`.
- Tabelas devem incluir `data_hora_inclusao` e `data_hora_alteracao` (`TIMESTAMPTZ`, defaults em `now()`, trigger de atualização). Use `src/core/db_schema.ensure_audit_columns()` ao criar novas tabelas para manter o padrão.

## Estilo e práticas
- Imports absolutos `src.`; async/await para IO; evite `Any`.
- Comentários só quando necessário para entendimento.
- Não reformatar arquivos inteiros sem motivo; altere apenas o escopo tocado.
- Validação de entrada: e-mails no formato `xxx@dominio.xxx` ou `xxx@dominio.ccc.cc`; telefones em `(xx)nnnnnnnnn` ou `+xx(nnnnnnnnn)` com 7–12 dígitos. Sempre validar ao capturar/persistir esses campos.

## Testes/validação
- Preferir `pytest` e `pytest-asyncio` para lógica nova; coloque testes em `tests/`.
- Use base de dados de teste (ex.: `sqlite+aiosqlite:///:memory:`) e limpe caches de settings/engine nos fixtures.
- Faça smoke tests manuais quando alterar fluxo crítico (login, banco, webhooks) e relate no resumo.
- Se não for possível automatizar (UI pura), descreva o gap e sugira como testar manualmente.
- Se adicionar scripts, inclua instruções de uso no README ou no próprio script.
- Para E2E/Streamlit, use Playwright headless opt-in (`RUN_E2E=1 pytest -q tests/e2e`) e suba o app em porta dedicada; documente dependências.
