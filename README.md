# CRM AI Plus

## Requisitos
- Python 3.12 instalado.
- PostgreSQL acessível conforme `DATABASE_URL` do `.env`.

## Preparar ambiente
1) Criar e ativar venv:
   - `python -m venv venv`
   - `source venv/bin/activate`
2) Instalar dependências:
   - `pip install -r requirements.txt`
3) Configurar variáveis:
   - `cp .env.example .env`
   - Preencher em `.env`: `DATABASE_URL`, `REDIS_URL`, `CHROMA_HOST`, `OPENAI_API_KEY`.

## Executar backend (FastAPI)
- `python -m uvicorn src.backend.main:app --reload --port 8000`

## Executar plataforma Workspace (Streamlit)
1) Certifique-se de que o `.env` está preenchido e o Postgres acessível.
2) (Opcional) mantenha o backend rodando em outro terminal para testes de webhook.
3) Inicie o Streamlit:
   - `streamlit run src/frontend/app.py`
4) A página exibirá:
   - Título “CRM AI Plus - Workspace”.
   - Resultado do teste de conexão ao banco (`SELECT 1`): verde se OK, vermelho se falhar.
   - O app solicitará login; se não houver usuário cadastrado, crie o primeiro. Senha mínima de 6 caracteres.
   - Para Chatwoot, cadastre os parâmetros em Gestão > Parâmetros Chatwoot (não usa mais variáveis de ambiente para Chatwoot).

## Criar/alterar usuário via CLI
- Com o venv ativo:
  - Criar: `python -m src.scripts.create_user --username admin --full-name "Admin" --email admin@example.com --role ADMIN`
  - Atualizar senha: `python -m src.scripts.create_user --username admin --update`
  - Você será solicitado a digitar a senha (ou use `--password`). Informe também nome completo, e-mail e (opcional) tipo de usuário (ADMIN/USER). Senha mínima de 6 caracteres. Usa PBKDF2 para armazenar hash.

## Expor para Chatwoot (ngrok)
- `ngrok http 8000`
- Configure o webhook no Chatwoot para `https://<subdomínio-ngrok>/api/v1/webhooks/chatwoot` ouvindo eventos `message_created`.

## Smoke test Fase 1 (Chatwoot)
- Envie uma mensagem como cliente em uma conversa; o backend deve logar o evento e responder com “Recebi sua mensagem!” na mesma conversa.
