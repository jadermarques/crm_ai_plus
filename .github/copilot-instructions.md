# CRM AI Plus - AI Coding Agent Instructions

## Project Overview
CRM AI Plus is a customer relationship management system with AI-powered chat responses, integrating Chatwoot for messaging. It uses FastAPI for backend webhooks, Streamlit for workspace UI, PostgreSQL for data, Redis for caching, ChromaDB for vector storage, and OpenAI for AI responses.

## Architecture
- **Backend** (`src/backend/`): FastAPI app handling Chatwoot webhooks at `/api/v1/webhooks/chatwoot`. Processes incoming messages and sends AI-generated replies.
- **Frontend** (`src/frontend/`): Streamlit app for workspace management, tests database connectivity on load.
- **Core** (`src/core/`): Shared utilities - `config.py` for Pydantic settings from `.env`, `database.py` for async SQLAlchemy with PostgreSQL.
- **Modules** (`src/modules/`): Extensible components, currently `common/` placeholder.

Key data flows: Chatwoot webhook → FastAPI → AI processing (future) → Response back to Chatwoot.

## Key Workflows
- **Run Backend**: `python -m uvicorn src.backend.main:app --reload --port 8000`
- **Run Frontend**: `streamlit run src/frontend/app.py`
- **Expose for Chatwoot**: Use ngrok `ngrok http 8000`, configure webhook URL `https://<ngrok-url>/api/v1/webhooks/chatwoot`
- **Setup**: Create venv, install from `requirements.txt`, copy `.env.example` to `.env` with required vars (DATABASE_URL, etc.)

## Conventions and Patterns
- **Async Everywhere**: Use async/await for DB operations, HTTP calls. Example: `async with engine.connect() as conn:`
- **Settings Management**: Use `get_settings()` from `src.core.config` for env vars, cached with `@lru_cache`.
- **Database**: Async SQLAlchemy with `get_engine()` and `get_sessionmaker()` cached. Use `async with session_factory() as session:` for transactions.
- **Imports**: Absolute imports from `src.`, e.g., `from src.core.database import get_engine`.
- **Error Handling**: Log exceptions, return JSON responses with status codes in FastAPI routes.
- **AI Integration**: Use Pydantic AI for structured AI responses, ChromaDB for vector similarity searches.

## Examples
- Add new webhook: Include router in `main.py` `app.include_router(new_router)`.
- DB query: `async with get_sessionmaker()() as session: result = await session.execute(text("SELECT * FROM table"))`
- HTTP client: `async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, 10.0)) as client: response = await client.post(url, json=data)`

Reference: [README.md](README.md) for setup, [src/backend/api/webhooks.py](src/backend/api/webhooks.py) for Chatwoot integration.</content>
<parameter name="filePath">/home/jader/projects/crm_ai_plus/.github/copilot-instructions.md