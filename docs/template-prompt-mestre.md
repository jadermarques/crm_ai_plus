# Template de Prompt Mestre (CRM AI Plus)

Copie e preencha os campos abaixo ao pedir novas funcionalidades. Mantenha mensagens em português e siga os padrões deste projeto.

- **Contexto do projeto**: CRM AI Plus; frontend Streamlit com navegação modular/ícones; backend FastAPI webhooks; Postgres assíncrono via `get_engine`/`get_sessionmaker`; configs via `get_settings()`/.env; padrões em `.github/copilot-instructions.md`, `AGENTS.md`, `docs/guidelines.md`.
- **Objetivo**: o que entregar (ex.: “nova tela de X”, “endpoint Y”, “ajustar fluxo Z”).
- **Entradas**: dados capturados (campos, tipos, validações, origem).
- **Saídas**: o que exibir/retornar (UI, JSON, mensagens).
- **Regras de negócio**: cálculos, prioridades, limites, cenários especiais.
- **Banco de dados**: tabelas novas/alteradas (nomes, colunas, tipos, nulos, defaults). Lembrar `data_hora_inclusao` e `data_hora_alteracao` com trigger; use `src/core/db_schema.ensure_audit_columns`.
- **UI/UX**: layout esperado, seções e ordem, labels/botões em português, uso de componentes/tema; preservar sidebar.
- **Integrações**: APIs externas (endpoints, payloads, auth), webhooks envolvidos.
- **Erros/feedback**: mensagens amigáveis e onde aparecem; estados vazio/loading.
- **Testes desejados**: unitários/pytest-asyncio, E2E opt-in `RUN_E2E=1`, cenários críticos (login sucesso/falha, credenciais inválidas).
- **Restrições**: não alterar `.env`/credenciais; não reformatar fora do escopo; imports `src.*`; usar async para IO; sem conexões manuais.
- **Não fazer**: itens explícitos a evitar (ex.: não mudar sidebar, não remover campo X).

Checklist rápido (opcional):
- [ ] Campos de auditoria incluídos em tabelas novas/alteradas.
- [ ] Mensagens em português e estrutura da sidebar mantida.
- [ ] Testes planejados/solicitados (unitário/E2E) e logs em `logs/tests/<arquivo>.log`.
