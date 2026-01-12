# API Reference - CRM AI Plus

## Core Modules API

### agents.py

#### ensure_tables()
```python
async def ensure_tables() -> None
```
Cria as tabelas de agentes no banco de dados se não existirem.

---

#### ensure_default_agents()
```python
async def ensure_default_agents(model_name: str | None) -> None
```
Cria os agentes padrão do sistema se não existirem.

**Parâmetros:**
- `model_name`: Nome do modelo de IA a ser usado (ex: "gpt-4o-mini")

---

#### list_agents()
```python
async def list_agents(include_inactive: bool = True) -> list[dict]
```
Lista todos os agentes cadastrados.

**Retorno:**
```python
[{
    "id": 1,
    "pk": "abc123",
    "nome": "Agente Triagem",
    "descricao": "Descrição do agente",
    "system_prompt": "Prompt do sistema...",
    "versao": 1,
    "ativo": True,
    "agente_orquestrador": True,
    "papel": "triagem",
    "model": "gpt-4o-mini",
    "rag_id": None
}, ...]
```

---

#### create_agent()
```python
async def create_agent(
    *,
    nome: str,
    descricao: str | None,
    system_prompt: str,
    model: str,
    versao: int | float | None = None,
    ativo: bool = True,
    agente_orquestrador: bool = False,
    papel: str | AgentRole | None = None,
    rag_id: int | None = None,
) -> dict
```
Cria um novo agente.

---

#### update_agent()
```python
async def update_agent(
    agent_id: int,
    *,
    nome: str,
    descricao: str | None,
    system_prompt: str,
    model: str,
    versao: int | float | None,
    ativo: bool = True,
    agente_orquestrador: bool = False,
    papel: str | AgentRole | None = None,
    rag_id: int | None = None,
) -> None
```
Atualiza um agente existente.

---

#### delete_agent()
```python
async def delete_agent(agent_id: int) -> None
```
Remove um agente pelo ID.

---

### bots.py

#### list_bots()
```python
async def list_bots(include_inactive: bool = True) -> list[dict]
```
Lista todos os bots cadastrados.

---

#### create_bot()
```python
async def create_bot(
    *,
    nome: str,
    descricao: str | None,
    versao: int | float | None = None,
    ativo: bool = True,
    persona: str | None = None,
) -> dict
```
Cria um novo bot.

---

#### replace_bot_agents()
```python
async def replace_bot_agents(
    bot_id: int,
    agent_ids: list[int],
    orchestrator_agent_id: int,
) -> None
```
Substitui os agentes vinculados a um bot.

---

#### list_bot_agents()
```python
async def list_bot_agents(bot_id: int) -> list[dict]
```
Lista os agentes vinculados a um bot.

**Retorno:**
```python
[{
    "agent_id": 1,
    "role": "orquestrador",  # ou "agente"
    "nome": "Agente Triagem",
    ...
}, ...]
```

---

### orchestration.py

#### run_orchestrator_reply()
```python
def run_orchestrator_reply(
    orchestrator_agent: dict,
    linked_agents: list[dict],
    agents_by_id: dict[int, dict],
    user_prompt: str,
    run_async_fn: callable,
    log_path: Path | str | None = None,
) -> tuple[str, dict, dict | None]
```
Executa o fluxo completo de orquestração.

**Retorno:** `(response_text, debug_info, usage_info)`

---

#### run_agent_raw()
```python
def run_agent_raw(
    agent_record: dict,
    user_prompt: str,
    context: AgentContext,
    run_async_fn: callable,
    log_path: Path | str | None = None,
) -> tuple[str | None, dict, dict | None]
```
Executa um agente diretamente.

**Retorno:** `(raw_response, rag_debug, usage_info)`

---

#### clean_reply_text()
```python
def clean_reply_text(text: str) -> str
```
Limpa artefatos de resposta (prefixos JSON, AgentReply, etc).

---

### auth.py

#### verify_credentials()
```python
async def verify_credentials(username: str, password: str) -> dict | None
```
Valida credenciais de login.

**Retorno:** Dados do usuário se válido, `None` se inválido.

---

#### create_user()
```python
async def create_user(
    username: str,
    password: str,
    *,
    full_name: str,
    email: str,
    role: str = "USER",
) -> dict
```
Cria um novo usuário.

---

### rag_management.py

#### list_rags()
```python
async def list_rags(include_inactive: bool = True) -> list[dict]
```
Lista todas as coleções RAG.

---

#### create_rag()
```python
async def create_rag(
    *,
    nome: str,
    rag_id: str,
    descricao: str | None,
    ativo: bool = True,
    provedor_rag: str,  # "RAG_OPENAI" ou "RAG_CHROMADB"
) -> dict
```
Cria uma nova coleção RAG.

---

## Modelos Pydantic

### AgentContext
```python
class AgentContext(BaseModel):
    mensagem: str           # Mensagem do cliente
    canal: str | None       # Canal de origem
    origem: str | None      # Origem da mensagem
    horario_local: str | None
    fora_horario: bool | None
    pediu_humano: bool = False
    nomes_citados: list[str] = []
    conversation_id: int | None
    inbox_id: int | None
    contact_id: int | None
    metadata: dict = {}
```

### RouteDecision
```python
class RouteDecision(BaseModel):
    agente_destino: AgentDestination
    confianca: float            # 0.0 a 1.0
    pergunta_clareadora: str | None
    mensagem_transicao: str | None
    precisa_humano: bool = False
    motivo: str
    intencao: str | None
    tags: list[str] = []
```

### AgentReply
```python
class AgentReply(BaseModel):
    acao: ReplyAction           # responder, perguntar, redirecionar, escalar_humano
    mensagem: str
    precisa_humano: bool = False
    motivo_escalacao: str | None
    dados_faltantes: list[str] = []
    tags: list[str] = []
```

---

## Constantes (constants.py)

```python
# Paths
PROJECT_ROOT           # Raiz do projeto
RAG_DATA_DIR          # Diretório de arquivos RAG
DEBUG_LOGS_DIR        # Diretório de logs de debug

# Mensagens padrão
DEFAULT_NO_RESPONSE = "(Sem resposta)"
DEFAULT_NO_RESPONSE_DOT = "Sem resposta."
DEFAULT_HANDOFF_MESSAGE = "Um atendente humano entrará em contato em breve."

# Limites
MAX_SAFETY_TURNS = 25  # Máximo de turnos na simulação

# Vozes TTS
VOICE_BOT = "pt-BR-FranciscaNeural"
VOICE_CLIENT = "pt-BR-AntonioNeural"
```

---

## Enums

### AgentRole
```python
class AgentRole(str, Enum):
    TRIAGEM = "triagem"
    COMERCIAL = "comercial"
    GUIA_UNIDADES = "guia_unidades"
    COTADOR = "cotador"
    CONSULTOR_TECNICO = "consultor_tecnico"
    RESUMO = "resumo"
    COORDENADOR = "coordenador"
    CLIENTE_SIMULADO_PADRAO = "cliente_simulado_padrao"
```

### ReplyAction
```python
class ReplyAction(str, Enum):
    RESPONDER = "responder"
    PERGUNTAR = "perguntar"
    REDIRECIONAR = "redirecionar"
    ESCALAR_HUMANO = "escalar_humano"
```

---

*API Reference - CRM AI Plus v1.0*
