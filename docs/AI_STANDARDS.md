# Padrão de Logging de LLM

**Data de Criação:** 2026-01-12
**Status:** Obrigatório

Todas as interações com modelos de linguagem (LLMs) no projeto `crm_ai_plus` **DEVEM** ser registradas no log global de prompts.

Isso é crucial para auditoria, debug e otimização de custos e performance dos prompts.

## Arquitetura de Log

O sistema utiliza um logger centralizado localizado em `src/core/debug_logger.py`.
O arquivo de log gerado é `logs/llm_history.log`.

## Como Implementar

Sempre que você criar uma nova função, classe ou script que chame uma API de LLM (OpenAI, Anthropic, Gemini, etc.), você deve importar e chamar a função `log_llm_interaction`.

### Assinatura da Função

```python
from src.core.debug_logger import log_llm_interaction

def log_llm_interaction(
    agent_name: str | None,
    model: str,
    system_prompt: str,
    user_prompt: str,
    response: str,
    usage: dict | None = None
) -> None:
    ...
```

### Exemplo de Uso

```python
from src.core.debug_logger import log_llm_interaction

# ... sua chamada ao LLM ...
result = await model.run(prompt)

# ... LOG OBRIGATÓRIO LOGO APÓS O RESULTADO ...
log_llm_interaction(
    agent_name="MeuNovoAgente",
    model="gpt-4",
    system_prompt="Você é um assistente útil.",
    user_prompt=prompt,
    response=result.text,
    usage={
        "input": result.usage.input_tokens,
        "output": result.usage.output_tokens,
        "total": result.usage.total_tokens
    }
)
```

## Locais Já Cobertos

- **Orquestrador Central** (`src/core/orchestration.py`): Todas as chamadas via `Agent` padrão.
- **Simulador de Bot** (`src/frontend/views/bot_simulator.py`): Todas as interações simuladas.
- **Teste de Conexão** (`src/core/ia_settings.py`): Testes de ping em novos modelos.

## Checklist para Novas Funcionalidades

- [ ] A funcionalidade usa LLM?
- [ ] O código importa `log_llm_interaction`?
- [ ] O log é chamado **após** a resposta do modelo (sucesso)?
- [ ] O log inclui System Prompt, User Prompt e Resposta?

## Padrão de Implementação de Bots

**Regra Persistente (Ordem de Prompt):**

Sempre que a execução envolver um **Bot** (entidade que agrupa agentes), o prompt do Sistema (System Prompt) **DEVE** ser construído na seguinte ordem:

1. **Persona do Bot** (Instruções GLOBAIS): Define a identidade principal (ex: "Você é o Galo Bot...").
2. **Prompt do Agente** (Instruções Específicas): Define a função atual (ex: "Você é o Agente de Triagem...").
3. **Contexto da Sessão**: Histórico, variáveis, etc.

**Implementação Obrigatória:**
```python
parts = []
# 1. PERSONA (OBRIGATÓRIO PRIMEIRO)
if bot_persona:
    parts.append(f"=== INSTRUÇÕES GLOBAIS (PERSONA) ===\n{bot_persona}")

# 2. AGENTE
if agent_prompt:
    parts.append(f"=== INSTRUÇÕES DO AGENTE ===\n{agent_prompt}")

# ... resto ...
system_prompt = "\n\n".join(parts)
```
Isso garante que a personalidade do Bot prevaleça sobre comportamentos genéricos do agente.
