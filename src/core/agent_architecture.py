from __future__ import annotations

from enum import Enum
from typing import Any, TypeVar
import unicodedata

from pydantic import BaseModel, Field, model_validator
from pydantic_ai import Agent, RunContext

ResultT = TypeVar("ResultT", bound=BaseModel)


class AgentRole(str, Enum):
    TRIAGEM = "triagem"
    COMERCIAL = "comercial"
    GUIA_UNIDADES = "guia_unidades"
    COTADOR = "cotador"
    CONSULTOR_TECNICO = "consultor_tecnico"
    RESUMO = "resumo"
    COORDENADOR = "coordenador"


class AgentDestination(str, Enum):
    COMERCIAL = "comercial"
    GUIA_UNIDADES = "guia_unidades"
    COTADOR = "cotador"
    CONSULTOR_TECNICO = "consultor_tecnico"
    RESUMO = "resumo"
    COORDENADOR = "coordenador"
    HUMANO = "humano"


class ReplyAction(str, Enum):
    RESPONDER = "responder"
    PERGUNTAR = "perguntar"
    REDIRECIONAR = "redirecionar"
    ESCALAR_HUMANO = "escalar_humano"


class AgentContext(BaseModel):
    mensagem: str = Field(min_length=1, description="Mensagem recebida do cliente.")
    canal: str | None = None
    origem: str | None = None
    horario_local: str | None = None
    fora_horario: bool | None = None
    pediu_humano: bool = False
    nomes_citados: list[str] = Field(default_factory=list)
    conversation_id: int | None = None
    inbox_id: int | None = None
    contact_id: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RouteDecision(BaseModel):
    agente_destino: AgentDestination
    confianca: float = Field(ge=0.0, le=1.0)
    pergunta_clareadora: str | None = None
    precisa_humano: bool = False
    motivo: str = Field(min_length=1)
    intencao: str | None = None
    tags: list[str] = Field(default_factory=list)


class AgentReply(BaseModel):
    acao: ReplyAction = ReplyAction.RESPONDER
    mensagem: str = Field(min_length=1)
    precisa_humano: bool = False
    motivo_escalacao: str | None = None
    dados_faltantes: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_escalation(self) -> "AgentReply":
        if self.acao == ReplyAction.ESCALAR_HUMANO and not self.precisa_humano:
            raise ValueError("precisa_humano deve ser True quando acao=escalar_humano.")
        if self.precisa_humano and not (self.motivo_escalacao or "").strip():
            raise ValueError("Informe motivo_escalacao ao escalar para humano.")
        return self


class HandoffSummary(BaseModel):
    resumo: str = Field(min_length=1)
    dados_relevantes: list[str] = Field(default_factory=list)
    pendencias: list[str] = Field(default_factory=list)
    sentimento: str | None = None
    sugestao_proxima_acao: str | None = None


class CoordinatorDecision(BaseModel):
    acao: ReplyAction
    mensagem: str | None = None
    agente_destino: AgentDestination | None = None
    precisa_resumo: bool = False
    motivo: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_decision(self) -> "CoordinatorDecision":
        if self.acao in {ReplyAction.RESPONDER, ReplyAction.PERGUNTAR}:
            if not (self.mensagem or "").strip():
                raise ValueError("mensagem e obrigatoria quando acao exige resposta.")
        if self.acao == ReplyAction.REDIRECIONAR and self.agente_destino is None:
            raise ValueError("agente_destino e obrigatorio quando acao=redirecionar.")
        if self.acao == ReplyAction.ESCALAR_HUMANO:
            if self.agente_destino != AgentDestination.HUMANO:
                raise ValueError("agente_destino deve ser humano quando acao=escalar_humano.")
        return self


AGENT_DISPLAY_NAMES: dict[AgentRole, str] = {
    AgentRole.TRIAGEM: "Agente Triagem",
    AgentRole.COMERCIAL: "Agente Comercial",
    AgentRole.GUIA_UNIDADES: "Agente Guia de Unidades",
    AgentRole.COTADOR: "Agente Cotador",
    AgentRole.CONSULTOR_TECNICO: "Agente Consultor Técnico",
    AgentRole.RESUMO: "Agente Resumo",
    AgentRole.COORDENADOR: "Agente Coordenador",
}

AGENT_DESCRIPTIONS: dict[AgentRole, str] = {
    AgentRole.TRIAGEM: "Roteamento inicial e classificacao do atendimento.",
    AgentRole.COMERCIAL: "Conducao comercial com foco em fechamento de vendas.",
    AgentRole.GUIA_UNIDADES: "Informacoes sobre lojas, enderecos e contatos.",
    AgentRole.COTADOR: "Consulta de precos e servicos das lojas.",
    AgentRole.CONSULTOR_TECNICO: "Orientacao tecnica sobre produtos e servicos.",
    AgentRole.RESUMO: "Resumo do atendimento para o humano assumir.",
    AgentRole.COORDENADOR: "Decisoes e escalonamento em casos complexos.",
}

DEFAULT_AGENT_ORDER: list[AgentRole] = [
    AgentRole.TRIAGEM,
    AgentRole.COMERCIAL,
    AgentRole.GUIA_UNIDADES,
    AgentRole.COTADOR,
    AgentRole.CONSULTOR_TECNICO,
    AgentRole.RESUMO,
    AgentRole.COORDENADOR,
]


AGENT_SYSTEM_PROMPTS: dict[AgentRole, str] = {
    AgentRole.TRIAGEM: (
        "Voce e o Agente Triagem do CRM AI Plus.\n"
        "Sua tarefa e analisar a mensagem do cliente e decidir o melhor agente destino.\n"
        "Responda SOMENTE usando o contrato RouteDecision.\n"
        "Regras:\n"
        "- Se pediu_humano for True ou houver nomes_citados, escolha agente_destino=humano "
        "e precisa_humano=True.\n"
        "- Se fora_horario for True, registre isso no motivo e priorize rotas seguras.\n"
        "- Se a intencao estiver ambigua, use pergunta_clareadora e escolha "
        "agente_destino=coordenador.\n"
        "- Nunca invente informacoes e nao responda diretamente ao cliente.\n"
    ),
    AgentRole.COMERCIAL: (
        "Voce e o Agente Comercial. Conduza o atendimento com foco em fechar a venda.\n"
        "Responda SEMPRE usando o contrato AgentReply.\n"
        "Nao invente precos, estoque ou prazos. Se faltar informacao, "
        "use acao=perguntar e preencha dados_faltantes.\n"
        "Se o cliente pedir humano, defina precisa_humano=True e motivo_escalacao.\n"
    ),
    AgentRole.GUIA_UNIDADES: (
        "Voce e o Agente Guia de Unidades. Responda sobre enderecos, horarios, contatos "
        "e referencias das lojas.\n"
        "Responda SEMPRE usando o contrato AgentReply.\n"
        "Se faltar cidade, bairro ou unidade, use acao=perguntar e dados_faltantes.\n"
        "Nao invente informacoes. Se nao houver dados confiaveis, sinalize precisa_humano.\n"
    ),
    AgentRole.COTADOR: (
        "Voce e o Agente Cotador. Responda sobre precos e servicos.\n"
        "Responda SEMPRE usando o contrato AgentReply.\n"
        "Use apenas dados confiaveis (RAG ou sistemas). Se nao houver dados, "
        "pergunte o necessario ou escale para humano.\n"
    ),
    AgentRole.CONSULTOR_TECNICO: (
        "Voce e o Agente Consultor Técnico. Esclareca duvidas tecnicas, compatibilidade "
        "e vantagens de produtos e servicos.\n"
        "Responda SEMPRE usando o contrato AgentReply.\n"
        "Solicite dados do veiculo quando necessario. Nao invente informacoes.\n"
    ),
    AgentRole.RESUMO: (
        "Voce e o Agente Resumo. Gere um resumo objetivo para o humano assumir o caso.\n"
        "Responda SOMENTE usando o contrato HandoffSummary.\n"
        "Nao responda ao cliente e nao invente informacoes.\n"
    ),
    AgentRole.COORDENADOR: (
        "Voce e o Agente Coordenador. Decide a melhor acao quando houver duvidas "
        "ou falhas no atendimento.\n"
        "Responda SEMPRE usando o contrato CoordinatorDecision.\n"
        "- Se redirecionar, informe agente_destino.\n"
        "- Se escalar humano, defina agente_destino=humano e precisa_resumo=True.\n"
        "- Se perguntar, inclua uma pergunta objetiva em mensagem.\n"
    ),
}


def render_context(deps: AgentContext) -> str:
    fora_horario = "-"
    if deps.fora_horario is True:
        fora_horario = "sim"
    elif deps.fora_horario is False:
        fora_horario = "nao"

    lines = [
        f"Mensagem do cliente: {deps.mensagem}",
        f"Canal: {deps.canal or '-'}",
        f"Origem: {deps.origem or '-'}",
        f"Horario local: {deps.horario_local or '-'}",
        f"Fora do horario: {fora_horario}",
        f"Pediu humano: {'sim' if deps.pediu_humano else 'nao'}",
    ]
    if deps.nomes_citados:
        lines.append(f"Nomes citados: {', '.join(deps.nomes_citados)}")
    if deps.conversation_id:
        lines.append(f"Conversation ID: {deps.conversation_id}")
    if deps.inbox_id:
        lines.append(f"Inbox ID: {deps.inbox_id}")
    if deps.contact_id:
        lines.append(f"Contact ID: {deps.contact_id}")
    if deps.metadata:
        lines.append(f"Metadados: {deps.metadata}")
    return "\n".join(lines)


def render_system_prompt(role: AgentRole, deps: AgentContext) -> str:
    base_prompt = AGENT_SYSTEM_PROMPTS[role]
    context = render_context(deps)
    return f"{base_prompt}\nContexto do atendimento:\n{context}"


def _build_agent(
    role: AgentRole,
    model_name: str,
    result_type: type[ResultT],
) -> Agent[AgentContext, ResultT]:
    agent = Agent(
        model_name,
        result_type=result_type,
        deps_type=AgentContext,
        name=AGENT_DISPLAY_NAMES[role],
        defer_model_check=True,
    )

    @agent.system_prompt
    def _prompt(ctx: RunContext[AgentContext]) -> str:
        return render_system_prompt(role, ctx.deps)

    return agent


def build_agent(role: AgentRole, model_name: str) -> Agent:
    if role == AgentRole.TRIAGEM:
        return _build_agent(role, model_name, RouteDecision)
    if role == AgentRole.RESUMO:
        return _build_agent(role, model_name, HandoffSummary)
    if role == AgentRole.COORDENADOR:
        return _build_agent(role, model_name, CoordinatorDecision)
    return _build_agent(role, model_name, AgentReply)


def build_agents(model_name: str) -> dict[AgentRole, Agent]:
    return {role: build_agent(role, model_name) for role in AgentRole}


def resolve_role_label(value: Any) -> AgentRole | None:
    label = _normalize_label(value)
    if not label:
        return None
    if "humano" in label or "atendente" in label:
        return None
    label_underscore = label.replace(" ", "_")
    for role in AgentRole:
        if label == role.value or label_underscore == role.value:
            return role
    if "triagem" in label:
        return AgentRole.TRIAGEM
    if "comercial" in label or "venda" in label:
        return AgentRole.COMERCIAL
    if "guia" in label or "unidade" in label or "loja" in label:
        return AgentRole.GUIA_UNIDADES
    if "cotador" in label or "cotacao" in label or "preco" in label:
        return AgentRole.COTADOR
    if "consultor" in label or "tecnico" in label:
        return AgentRole.CONSULTOR_TECNICO
    if "resumo" in label:
        return AgentRole.RESUMO
    if "coordenador" in label or "supervisor" in label:
        return AgentRole.COORDENADOR
    return None


def _normalize_label(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    normalized = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return normalized.replace("_", " ")
