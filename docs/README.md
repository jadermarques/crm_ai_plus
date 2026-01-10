# CRM AI Plus - Documentação Técnica

## Visão Geral

O CRM AI Plus é uma plataforma de gerenciamento de relacionamento com clientes potencializada por Inteligência Artificial. O sistema utiliza múltiplos agentes de IA especializados para automatizar e otimizar o atendimento ao cliente.

---

## Arquitetura do Sistema

```mermaid
graph TB
    subgraph Frontend["Frontend (Streamlit)"]
        APP[app.py]
        VIEWS[Views]
        SHARED[shared.py]
    end
    
    subgraph Core["Core Business Logic"]
        AGENTS[agents.py]
        BOTS[bots.py]
        ORCH[orchestration.py]
        ARCH[agent_architecture.py]
        AUTH[auth.py]
        RAG[rag_management.py]
    end
    
    subgraph Backend["Backend (FastAPI)"]
        API[API Endpoints]
    end
    
    subgraph External["Serviços Externos"]
        OPENAI[OpenAI API]
        CHROMA[ChromaDB]
        DB[(PostgreSQL)]
    end
    
    APP --> VIEWS
    VIEWS --> CORE
    VIEWS --> ORCH
    ORCH --> ARCH
    AGENTS --> DB
    BOTS --> DB
    AUTH --> DB
    RAG --> CHROMA
    ARCH --> OPENAI
```

---

## Estrutura de Diretórios

```
crm_ai_plus/
├── src/
│   ├── core/                    # Lógica de negócio
│   │   ├── agent_architecture.py  # Modelos Pydantic e prompts
│   │   ├── agents.py              # CRUD de agentes
│   │   ├── auth.py                # Autenticação de usuários
│   │   ├── bots.py                # CRUD de bots
│   │   ├── config.py              # Configurações
│   │   ├── constants.py           # Constantes centralizadas
│   │   ├── database.py            # Conexão PostgreSQL
│   │   ├── debug_logger.py        # Logging de debug
│   │   ├── ia_settings.py         # Provedores e modelos de IA
│   │   ├── management.py          # Módulos e permissões
│   │   ├── orchestration.py       # Orquestração de agentes
│   │   ├── rag_management.py      # Gerenciamento RAG
│   │   └── rag_utils.py           # Utilitários RAG
│   │
│   ├── frontend/                # Interface Streamlit
│   │   ├── app.py                 # Aplicação principal
│   │   ├── shared.py              # Componentes compartilhados
│   │   ├── config/                # Configurações UI
│   │   └── views/                 # Páginas da aplicação
│   │
│   └── backend/                 # API FastAPI
│       └── main.py                # Endpoints REST
│
├── data/
│   └── rag_files/               # Arquivos RAG locais
│
├── logs/
│   └── debug_runs/              # Logs de debug
│
├── docs/                        # Documentação
└── tests/                       # Testes automatizados
```

---

## Módulos Core

### agent_architecture.py
Define a arquitetura de agentes de IA.

**Classes Principais:**
| Classe | Descrição |
|--------|-----------|
| `AgentRole` | Enum com papéis de agentes |
| `AgentDestination` | Enum com destinos de roteamento |
| `AgentContext` | Contexto da conversa |
| `RouteDecision` | Decisão de roteamento do triagem |
| `AgentReply` | Resposta padronizada de agentes |
| `CoordinatorDecision` | Decisão do coordenador |
| `HandoffSummary` | Resumo para handoff humano |

**Funções:**
- `build_agent()` - Constrói agente pydantic-ai
- `resolve_role_label()` - Resolve label de papel para enum
- `render_context()` - Renderiza contexto para prompt

---

### agents.py
Gerencia agentes de IA no banco de dados.

**Funções CRUD:**
| Função | Descrição |
|--------|-----------|
| `create_agent()` | Cria novo agente |
| `update_agent()` | Atualiza agente existente |
| `delete_agent()` | Remove agente |
| `list_agents()` | Lista todos os agentes |
| `ensure_default_agents()` | Cria agentes padrão |

**Tabela: agents**
```sql
id, pk, nome, descricao, system_prompt, 
versao, ativo, agente_orquestrador, papel, 
model, rag_id, data_hora_inclusao, data_hora_alteracao
```

---

### bots.py
Gerencia bots e seus agentes vinculados.

**Funções CRUD:**
| Função | Descrição |
|--------|-----------|
| `create_bot()` | Cria novo bot |
| `update_bot()` | Atualiza bot |
| `delete_bot()` | Remove bot |
| `list_bots()` | Lista todos os bots |
| `replace_bot_agents()` | Vincula agentes ao bot |
| `list_bot_agents()` | Lista agentes do bot |

**Tabelas:**
- `bots` - Configuração do bot
- `bot_agents` - Vínculo bot-agente

---

### orchestration.py
Lógica central de orquestração de agentes.

**Funções Principais:**
| Função | Descrição |
|--------|-----------|
| `run_orchestrator_reply()` | Executa fluxo de orquestração |
| `run_agent_raw()` | Execução direta de agente |
| `run_agent_reply()` | Execução com processamento |
| `clean_reply_text()` | Limpeza de resposta |
| `extract_json()` | Extração de JSON |
| `sum_usage()` | Acumulador de tokens |

---

### auth.py
Sistema de autenticação de usuários.

**Funções:**
- `create_user()` / `update_user()` / `list_users()`
- `verify_credentials()` - Valida login
- `update_password()` - Atualiza senha
- `set_user_status()` - Ativa/desativa usuário

---

### rag_management.py
Gerenciamento de coleções RAG.

**Provedores Suportados:**
- `RAG_OPENAI` - OpenAI Assistants
- `RAG_CHROMADB` - ChromaDB local/remoto

**Funções:**
- `create_rag()` / `update_rag()` / `delete_rag()`
- `list_rags()` / `get_rag_by_id()`

---

## Frontend Views

### Principais Páginas

| View | Descrição |
|------|-----------|
| `bot_tests.py` | Playground de testes de bots |
| `bot_simulator.py` | Simulador automático |
| `agents.py` | Gerenciamento de agentes |
| `bots.py` | Gerenciamento de bots |
| `users.py` | Gerenciamento de usuários |
| `ia_configs.py` | Configurações de IA |
| `rag_management.py` | Gerenciamento RAG |

---

## Fluxo de Orquestração

```mermaid
sequenceDiagram
    participant C as Cliente
    participant T as Triagem
    participant Co as Coordenador
    participant A as Agente Especialista
    
    C->>T: Mensagem inicial
    T->>T: Analisa intenção
    alt Intenção clara
        T->>A: Roteia para especialista
        A->>C: Resposta direta
    else Intenção ambígua
        T->>Co: Encaminha para coordenador
        Co->>Co: Decide melhor ação
        Co->>A: Delega para agente
        A->>C: Resposta
    else Precisa humano
        T->>C: Handoff para atendente
    end
```

---

## Configuração

### Variáveis de Ambiente
```bash
# Banco de dados
DATABASE_URL=postgresql://user:pass@host:5432/db

# OpenAI
OPENAI_API_KEY=sk-...

# ChromaDB
CHROMA_HOST=http://localhost:8000

# Desenvolvimento
DEV_AUTO_LOGIN=1
DEV_AUTO_LOGIN_USER=admin
```

### Execução
```bash
# Backend API
uvicorn src.backend.main:app --reload --port 8000

# Frontend Streamlit
streamlit run src/frontend/app.py
```

---

## Papéis de Agentes

| Papel | Enum | Função |
|-------|------|--------|
| Triagem | `TRIAGEM` | Orquestrador principal, roteia mensagens |
| Comercial | `COMERCIAL` | Vendas e negociação |
| Guia Unidades | `GUIA_UNIDADES` | Informações sobre unidades |
| Cotador | `COTADOR` | Geração de cotações |
| Consultor Técnico | `CONSULTOR_TECNICO` | Suporte técnico |
| Resumo | `RESUMO` | Gera resumos de conversas |
| Coordenador | `COORDENADOR` | Coordena fluxos complexos |
| Cliente Simulado | `CLIENTE_SIMULADO_PADRAO` | Simulação para testes |

---

## Modelos de Dados (Pydantic)

### RouteDecision
```python
class RouteDecision(BaseModel):
    agente_destino: AgentDestination
    confianca: float  # 0.0 - 1.0
    pergunta_clareadora: str | None
    mensagem_transicao: str | None
    precisa_humano: bool
    motivo: str
    intencao: str | None
    tags: list[str]
```

### AgentReply
```python
class AgentReply(BaseModel):
    acao: ReplyAction
    mensagem: str
    precisa_humano: bool
    motivo_escalacao: str | None
    dados_faltantes: list[str]
    tags: list[str]
```

---

*Documentação gerada em 2026-01-09*
