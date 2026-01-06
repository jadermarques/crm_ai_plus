# Diretrizes de Desenvolvimento

## Setup
- Use Python 3.12, venv e `pip install -r requirements.txt`.
- Copie `.env.example` para `.env` e preencha `DATABASE_URL` (Postgres async), `REDIS_URL`, `CHATWOOT_*`, `OPENAI_API_KEY`, `CHROMA_HOST`.

## Backend (FastAPI)
- Entrypoint: `src/backend/main.py`; webhooks em `src/backend/api/`.
- Sempre async; use `get_settings()` e `get_sessionmaker()`; nada de conexões manuais.
- Respostas JSON com códigos adequados; logar erros.

## Frontend (Streamlit)
- App em `src/frontend/app.py`; páginas em `src/frontend/views/`.
- Autenticação: usuários no Postgres com hash PBKDF2; mínimo 6 caracteres; criação/alteração via CLI `src/scripts/create_user.py`.
- Mensagens ao usuário em português; mantenha navegação por módulos na sidebar.

## Banco e Config
- Helpers em `src/core/database.py` (engine por loop) e `src/core/config.py` (Pydantic Settings).
- Não hardcode segredos; tudo via `.env`.

## Estilo e práticas
- Imports absolutos `src.`; async/await para IO; evite `Any`.
- Comentários só quando necessário para entendimento.
- Não reformatar arquivos inteiros sem motivo; altere apenas o escopo tocado.

## Testes/validação
- Preferir `pytest` e `pytest-asyncio` para lógica nova; coloque testes em `tests/`.
- Use base de dados de teste (ex.: `sqlite+aiosqlite:///:memory:`) e limpe caches de settings/engine nos fixtures.
- Faça smoke tests manuais quando alterar fluxo crítico (login, banco, webhooks) e relate no resumo.
- Se não for possível automatizar (UI pura), descreva o gap e sugira como testar manualmente.
- Se adicionar scripts, inclua instruções de uso no README ou no próprio script.
- Para E2E/Streamlit, use Playwright headless opt-in (`RUN_E2E=1 pytest -q tests/e2e`) e suba o app em porta dedicada; documente dependências.
