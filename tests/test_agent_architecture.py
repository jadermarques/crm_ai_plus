from __future__ import annotations

import logging

import pytest
from pydantic import ValidationError

from src.core.agent_architecture import (
    AgentContext,
    AgentDestination,
    AgentReply,
    AgentRole,
    CoordinatorDecision,
    ReplyAction,
    RouteDecision,
    render_system_prompt,
)

logger = logging.getLogger(__name__)


def test_route_decision_confidence_bounds() -> None:
    logger.info("Validando confianca dentro do intervalo permitido")
    decision = RouteDecision(
        agente_destino=AgentDestination.COMERCIAL,
        confianca=0.8,
        motivo="Cliente demonstrou interesse em compra.",
    )
    assert decision.confianca == 0.8

    logger.info("Validando confianca acima do maximo gera erro")
    with pytest.raises(ValidationError):
        RouteDecision(
            agente_destino=AgentDestination.COTADOR,
            confianca=1.2,
            motivo="Teste invalido.",
        )

    logger.info("Validando confianca abaixo do minimo gera erro")
    with pytest.raises(ValidationError):
        RouteDecision(
            agente_destino=AgentDestination.GUIA_UNIDADES,
            confianca=-0.1,
            motivo="Teste invalido.",
        )


def test_agent_reply_escalation_requires_reason() -> None:
    logger.info("Validando que escalacao exige motivo")
    with pytest.raises(ValidationError):
        AgentReply(
            mensagem="Preciso transferir para humano.",
            precisa_humano=True,
        )

    logger.info("Validando que acao=escalar_humano exige precisa_humano")
    with pytest.raises(ValidationError):
        AgentReply(
            acao=ReplyAction.ESCALAR_HUMANO,
            mensagem="Transferindo para humano.",
            precisa_humano=False,
            motivo_escalacao="Solicitacao de humano.",
        )


def test_coordinator_requires_destination_on_redirect() -> None:
    logger.info("Validando que redirecionamento exige agente_destino")
    with pytest.raises(ValidationError):
        CoordinatorDecision(
            acao=ReplyAction.REDIRECIONAR,
            mensagem="Vou direcionar para o agente correto.",
            motivo="Cliente solicitou informacoes de unidades.",
        )

    logger.info("Validando que escalacao exige agente_destino humano")
    with pytest.raises(ValidationError):
        CoordinatorDecision(
            acao=ReplyAction.ESCALAR_HUMANO,
            motivo="Cliente pediu humano explicitamente.",
        )


def test_render_system_prompt_includes_context() -> None:
    logger.info("Validando contexto no prompt do agente")
    deps = AgentContext(
        mensagem="Ola, gostaria de saber preco de pneus.",
        canal="whatsapp",
        origem="site",
        horario_local="2024-10-12 10:30",
        fora_horario=False,
        pediu_humano=False,
        nomes_citados=["Maria"],
        conversation_id=123,
    )
    prompt = render_system_prompt(AgentRole.TRIAGEM, deps)
    assert "Mensagem do cliente: Ola, gostaria de saber preco de pneus." in prompt
    assert "Canal: whatsapp" in prompt
    assert "Origem: site" in prompt
    assert "Fora do horario: nao" in prompt
    assert "Nomes citados: Maria" in prompt
