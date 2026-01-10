# Guia de Desenvolvimento - CRM AI Plus

## Ambiente de Desenvolvimento

### Pré-requisitos
- Python 3.11+
- PostgreSQL 14+
- Node.js 18+ (opcional, para ferramentas de desenvolvimento)

### Setup Inicial
```bash
# Clone o repositório
git clone <repo-url>
cd crm_ai_plus

# Crie e ative o ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Instale as dependências
pip install -r requirements.txt

# Configure as variáveis de ambiente
cp .env.example .env
# Edite .env com suas credenciais
```

### Variáveis de Ambiente
```bash
DATABASE_URL=postgresql://user:pass@localhost:5432/crm_ai_plus
OPENAI_API_KEY=sk-...
CHROMA_HOST=http://localhost:8000

# Desenvolvimento
DEV_AUTO_LOGIN=1
DEV_AUTO_LOGIN_USER=admin
```

---

## Execução

### Backend (FastAPI)
```bash
python -m uvicorn src.backend.main:app --reload --port 8000
```

### Frontend (Streamlit)
```bash
streamlit run src/frontend/app.py
```

### Ambos (desenvolvimento)
```bash
# Terminal 1
python -m uvicorn src.backend.main:app --reload --port 8000

# Terminal 2
DEV_AUTO_LOGIN=1 DEV_AUTO_LOGIN_USER=admin streamlit run src/frontend/app.py
```

---

## Estrutura de Código

### Padrões de Nomenclatura
- **Funções privadas**: prefixo `_` (ex: `_normalize_name()`)
- **Constantes**: UPPER_SNAKE_CASE
- **Classes**: PascalCase
- **Variáveis**: snake_case

### Convenções de Arquivo
- **Core modules**: Lógica de negócio pura, sem UI
- **Views**: Apenas UI Streamlit, delega para core
- **Shared**: Componentes reutilizáveis

---

## Criando Novos Agentes

### 1. Adicione o papel ao enum
```python
# src/core/agent_architecture.py
class AgentRole(str, Enum):
    ...
    NOVO_AGENTE = "novo_agente"
```

### 2. Adicione o destino (se roteável)
```python
class AgentDestination(str, Enum):
    ...
    NOVO_AGENTE = "novo_agente"
```

### 3. Defina o prompt do sistema
```python
AGENT_SYSTEM_PROMPTS = {
    ...
    AgentRole.NOVO_AGENTE: (
        "Voce e o Agente Novo...\n"
        "Sua tarefa e...\n"
    ),
}
```

### 4. Atualize o banco de dados
```bash
python scripts/update_prompts_db.py
```

---

## Debug e Logs

### Habilitando Debug Logs
1. Na UI, marque a checkbox "Log debug completo"
2. Logs são salvos em `logs/debug_runs/`
3. Formato: `debug_YYYYMMDD_HHMMSS.jsonl`

### Verificando Logs
```python
import json
with open("logs/debug_runs/debug_XXXXX.jsonl") as f:
    for line in f:
        event = json.loads(line)
        print(event["event"], event["data"])
```

---

## Testes

### Executando Testes
```bash
pytest tests/ -v
```

### Estrutura de Testes
```
tests/
├── test_agents.py      # Testes de agentes
├── test_bots.py        # Testes de bots
├── test_auth.py        # Testes de autenticação
└── conftest.py         # Fixtures compartilhadas
```

---

## Contribuindo

### Workflow
1. Crie uma branch: `git checkout -b feature/nome-feature`
2. Faça suas alterações
3. Rode os testes: `pytest`
4. Commite: `git commit -m "feat: descrição"`
5. Push: `git push origin feature/nome-feature`
6. Abra um Pull Request

### Convenções de Commit
- `feat:` Nova funcionalidade
- `fix:` Correção de bug
- `docs:` Documentação
- `refactor:` Refatoração
- `test:` Testes

---

## Troubleshooting

### Erro de Conexão com Banco
```
sqlalchemy.exc.OperationalError: connection refused
```
**Solução:** Verifique se o PostgreSQL está rodando e se `DATABASE_URL` está correta.

### Erro de API Key
```
openai.AuthenticationError: Incorrect API key
```
**Solução:** Verifique `OPENAI_API_KEY` no `.env`.

### ChromaDB não encontrado
```
chromadb.errors.ChromaError: Collection not found
```
**Solução:** Verifique `CHROMA_HOST` e se a coleção existe.

---

*Guia de Desenvolvimento - CRM AI Plus*
