# Instruções do Agente

- Sempre consulte `.github/copilot-instructions.md` para contexto e padrões antes de alterar código.
- Mantenha mensagens da interface em português e preserve a navegação por módulos no Streamlit.
- Não altere configurações sensíveis (`.env`, credenciais) salvo pedido explícito.
- Para banco/Postgres use helpers `get_engine`/`get_sessionmaker`; evite criar conexões manuais.
- Senhas devem ter no mínimo 6 caracteres e ser armazenadas com hash PBKDF2 (passlib).
- Evite refatorações amplas não solicitadas; foque no escopo do pedido.
- Documente brevemente mudanças relevantes no resumo final.
- Sempre planeje/adicione testes unitários (pytest/pytest-asyncio) para novas regras; se não testar, cite o gap e sugira teste manual.
- Para UI/Streamlit, proponha teste E2E (Playwright/Selenium) quando viável; se não for implementar, registre o plano/manual e os gaps.
- Fluxos de login/autenticação devem ter testes de sucesso e falha (usuário inexistente, senha mínima, credencial inválida) atualizados ao alterar o código.
- Testes E2E devem ser headless e opt-in via variável (ex.: RUN_E2E=1); documente dependências (playwright) e como rodar.
- Inclua logs passo-a-passo nos testes (usar logging); pytest já está configurado com log_cli para exibir no terminal.
- Configure logs por módulo de teste (ex.: `logs/tests/<arquivo>.log`) além da saída no terminal.
- Só execute testes se o usuário solicitar explicitamente (ex.: “teste”, “faça testes” no pedido); caso contrário, apenas planeje/descreva. Se executar e falhar/for impossível, informe no resumo e como rodar.
- Sidebar do Streamlit: preservar o estilo/estrutura (módulos expandíveis com subitens e ícones) e só modificar se o usuário pedir.
