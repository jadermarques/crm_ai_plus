# Arquitetura de Agentes (PydanticAI)

Este documento descreve o contrato e os prompts base dos agentes definidos em
`src/core/agent_architecture.py`.

## Fluxo sugerido (Chatwoot -> agentes)

1. Webhook `message_created` recebe a mensagem do cliente.
2. Monte um `AgentContext` com dados do payload e metadados de canal/origem/horario.
3. Execute o `Agente Triagem` e leia o `RouteDecision`.
4. Chame o agente especialista indicado (Comercial, Guia de Unidades, Cotador ou Consultor Técnico).
5. Se houver duvida ou falha, chame o `Agente Coordenador`.
6. Se precisar de humano, gere o `HandoffSummary` com o `Agente Resumo` e envie como nota privada.

## Mapeamento recomendado de campos (Chatwoot -> AgentContext)

- `mensagem`: `payload["content"]`
- `conversation_id`: `payload["conversation"]["id"]` ou `payload["conversation_id"]`
- `inbox_id`: `payload["conversation"]["inbox_id"]`
- `contact_id`: `payload["sender"]["id"]`
- `canal`: `payload["conversation"]["channel"]`
- `origem`: `payload["conversation"]["meta"]["source"]` (se existir)
- `horario_local`: calculado a partir do timestamp + timezone do inbox
- `fora_horario`: calculado a partir de `working_hours` do inbox via API Chatwoot

## Exemplo rapido de uso

```python
from src.core.agent_architecture import AgentContext, AgentRole, build_agent

contexto = AgentContext(
    mensagem="Quero saber o preco do pneu 205/55.",
    canal="whatsapp",
    origem="ads",
    horario_local="2024-10-12 10:30",
    fora_horario=False,
    pediu_humano=False,
)

triagem = build_agent(AgentRole.TRIAGEM, model_name="gpt-4o-mini")
resultado = await triagem.run("Mensagem do cliente", deps=contexto)
decisao = resultado.data
```
