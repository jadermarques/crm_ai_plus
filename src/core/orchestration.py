"""
Orchestration Module - Shared Agent Execution Logic

This module centralizes the agent orchestration logic used by both
bot_tests.py and bot_simulator.py, eliminating code duplication.

Key Functions:
- run_orchestrator_reply: Main entry point for agent orchestration
- run_agent_raw: Low-level agent execution
- run_agent_reply: High-level agent response handler
- clean_reply_text: Response text cleanup utilities
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any, TYPE_CHECKING

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel

from src.core.agent_architecture import (
    AgentContext,
    AgentRole,
    AgentReply,
    CoordinatorDecision,
    HandoffSummary,
    RouteDecision,
    render_context,
    resolve_role_label,
)
from src.core.config import get_settings
from src.core.constants import (
    DEFAULT_AGENT_ERROR,
    DEFAULT_COORDINATOR_NOT_FOUND,
    DEFAULT_DESTINATION_NOT_FOUND,
    DEFAULT_DESTINATION_UNKNOWN,
    DEFAULT_HANDOFF_MESSAGE,
    DEFAULT_MODEL_NOT_CONFIGURED,
    DEFAULT_NO_RESPONSE_DOT,
)
from src.core.debug_logger import append_log, log_llm_interaction
from src.core.rag_management import RAG_PROVIDER_CHROMADB, RAG_PROVIDER_OPENAI

if TYPE_CHECKING:
    from src.frontend.shared import run_async


# -----------------------------------------------------------------------------
# Type Aliases
# -----------------------------------------------------------------------------
UsageDict = dict[str, int]
DebugDict = dict[str, Any]


# -----------------------------------------------------------------------------
# Main Orchestrator Entry Point
# -----------------------------------------------------------------------------
def run_orchestrator_reply(
    orchestrator_agent: dict[str, Any],
    linked_agents: list[dict[str, Any]],
    agents_by_id: dict[int, dict[str, Any]],
    user_prompt: str,
    run_async_fn: callable,
    log_path: Path | str | None = None,
) -> tuple[str, DebugDict, UsageDict | None]:
    """
    Execute the orchestrator agent and route to appropriate destination agent.
    
    Args:
        orchestrator_agent: The orchestrator agent configuration
        linked_agents: List of agents linked to the bot
        agents_by_id: Mapping of agent IDs to agent configs
        user_prompt: The user's message
        run_async_fn: Function to run async code (from frontend.shared)
        log_path: Optional path for debug logging
        
    Returns:
        Tuple of (response_text, debug_info, usage_info)
    """
    model_name = (orchestrator_agent.get("model") or "").strip()
    if not model_name:
        return DEFAULT_MODEL_NOT_CONFIGURED, {}, None

    context = AgentContext(
        mensagem=user_prompt,
        canal="playground",
        origem="playground",
    )
    debug_info = _init_debug_info(context, orchestrator_agent)
    agents_by_role = _map_agents_by_role(linked_agents, agents_by_id)

    # Execute router agent
    raw_reply, router_rag, usage_router = run_agent_raw(
        orchestrator_agent, user_prompt, context, run_async_fn, log_path=log_path
    )
    usage_total = sum_usage(None, usage_router)

    debug_info["roteador"] = _merge_rag_debug(_agent_debug(orchestrator_agent), router_rag)
    
    if raw_reply is None:
        debug_info["responder"] = debug_info["roteador"]
        debug_info["rag"] = router_rag
        return DEFAULT_AGENT_ERROR, debug_info, usage_total

    parsed = extract_json(raw_reply)
    debug_info["roteamento"] = _summarize_payload(parsed)

    if parsed is None:
        debug_info["responder"] = debug_info["roteador"]
        debug_info["resposta"] = _summarize_payload(None)
        debug_info["rag"] = router_rag
        return raw_reply or DEFAULT_NO_RESPONSE_DOT, debug_info, usage_total

    if _has_message(parsed):
        debug_info["responder"] = debug_info["roteador"]
        debug_info["resposta"] = _summarize_payload(parsed)
        debug_info["rag"] = router_rag
        return _extract_message(parsed) or DEFAULT_NO_RESPONSE_DOT, debug_info, usage_total

    destination = parsed.get("agente_destino")
    if not destination:
        debug_info["responder"] = debug_info["roteador"]
        debug_info["resposta"] = _summarize_payload(parsed)
        debug_info["rag"] = router_rag
        return raw_reply or DEFAULT_NO_RESPONSE_DOT, debug_info, usage_total

    if _needs_human(parsed, destination):
        debug_info["responder"] = debug_info["roteador"]
        debug_info["resposta"] = _summarize_payload(parsed)
        debug_info["rag"] = router_rag
        return _handoff_message(parsed), debug_info, usage_total

    clarifier = _string_or_none(parsed.get("pergunta_clareadora"))
    if clarifier:
        debug_info["responder"] = debug_info["roteador"]
        debug_info["resposta"] = _summarize_payload(parsed)
        debug_info["rag"] = router_rag
        return clarifier, debug_info, usage_total

    transition_msg = _string_or_none(parsed.get("mensagem_transicao"))

    destination_role = resolve_role_label(destination)
    if destination_role is None:
        debug_info["responder"] = debug_info["roteador"]
        debug_info["resposta"] = _summarize_payload(parsed)
        debug_info["rag"] = router_rag
        return DEFAULT_DESTINATION_UNKNOWN, debug_info, usage_total

    if destination_role == AgentRole.COORDENADOR:
        coordinator = agents_by_role.get(AgentRole.COORDENADOR)
        if not coordinator:
            debug_info["responder"] = debug_info["roteador"]
            debug_info["resposta"] = _summarize_payload(parsed)
            debug_info["rag"] = router_rag
            return DEFAULT_COORDINATOR_NOT_FOUND, debug_info, usage_total

        response_text, coordinator_payload, responder_agent, responder_payload, responder_rag, usage_coord = _run_coordinator_flow(
            coordinator, agents_by_role, user_prompt, context, run_async_fn, log_path=log_path
        )
        usage_total = sum_usage(usage_total, usage_coord)

        debug_info["coordenador"] = _summarize_payload(coordinator_payload)
        debug_info["responder"] = _merge_rag_debug(
            _agent_debug(responder_agent or coordinator),
            responder_rag,
        )
        debug_info["resposta"] = _summarize_payload(responder_payload)
        debug_info["rag"] = responder_rag

        if transition_msg:
            response_text = f"{transition_msg}\n\n{response_text}"
            if debug_info["responder"].get("nome"):
                debug_info["responder"]["nome"] = f"{orchestrator_agent['nome']} ▶ {debug_info['responder']['nome']}"

        return response_text, debug_info, usage_total

    destination_agent = agents_by_role.get(destination_role)
    if not destination_agent:
        debug_info["responder"] = debug_info["roteador"]
        debug_info["resposta"] = _summarize_payload(parsed)
        debug_info["rag"] = router_rag
        return DEFAULT_DESTINATION_NOT_FOUND, debug_info, usage_total

    response_text, responder_payload, responder_rag, usage_dest = run_agent_reply(
        destination_agent, user_prompt, context, run_async_fn, log_path=log_path
    )
    usage_total = sum_usage(usage_total, usage_dest)

    debug_info["responder"] = _merge_rag_debug(_agent_debug(destination_agent), responder_rag)
    debug_info["resposta"] = _summarize_payload(responder_payload)
    debug_info["rag"] = responder_rag

    if transition_msg:
        response_text = f"{transition_msg}\n\n{response_text}"
        if debug_info["responder"].get("nome"):
            debug_info["responder"]["nome"] = f"{orchestrator_agent['nome']} ▶ {debug_info['responder']['nome']}"

    return response_text, debug_info, usage_total


# -----------------------------------------------------------------------------
# Coordinator Flow
# -----------------------------------------------------------------------------
def _run_coordinator_flow(
    coordinator_agent: dict[str, Any],
    agents_by_role: dict[AgentRole, dict[str, Any]],
    user_prompt: str,
    context: AgentContext,
    run_async_fn: callable,
    log_path: Path | str | None = None,
) -> tuple[str, dict | None, dict | None, dict | None, dict, UsageDict | None]:
    """Execute coordinator agent and follow its decision."""
    raw_reply, rag_debug, usage = run_agent_raw(
        coordinator_agent, user_prompt, context, run_async_fn, log_path=log_path
    )
    
    if raw_reply is None:
        return DEFAULT_AGENT_ERROR, None, coordinator_agent, None, rag_debug, usage

    parsed = extract_json(raw_reply)
    if parsed is None:
        return raw_reply or DEFAULT_NO_RESPONSE_DOT, None, coordinator_agent, None, rag_debug, usage

    if _has_message(parsed):
        msg = _extract_message(parsed) or DEFAULT_NO_RESPONSE_DOT
        return msg, parsed, coordinator_agent, parsed, rag_debug, usage

    new_dest = parsed.get("agente_destino")
    if new_dest:
        dest_role = resolve_role_label(new_dest)
        if dest_role and dest_role in agents_by_role:
            dest_agent = agents_by_role[dest_role]
            reply_text, reply_payload, reply_rag, usage_dest = run_agent_reply(
                dest_agent, user_prompt, context, run_async_fn, log_path=log_path
            )
            usage = sum_usage(usage, usage_dest)
            return reply_text, parsed, dest_agent, reply_payload, reply_rag, usage

    return raw_reply or DEFAULT_NO_RESPONSE_DOT, parsed, coordinator_agent, None, rag_debug, usage


# -----------------------------------------------------------------------------
# Agent Execution
# -----------------------------------------------------------------------------
def run_agent_reply(
    agent_record: dict[str, Any],
    user_prompt: str,
    context: AgentContext,
    run_async_fn: callable,
    log_path: Path | str | None = None,
) -> tuple[str, dict | None, dict, UsageDict | None]:
    """Execute agent and process response."""
    raw_reply, rag_debug, usage = run_agent_raw(
        agent_record, user_prompt, context, run_async_fn, log_path=log_path
    )
    
    if raw_reply is None:
        return DEFAULT_AGENT_ERROR, None, rag_debug, usage

    parsed = extract_json(raw_reply)
    if parsed is None:
        return raw_reply or DEFAULT_NO_RESPONSE_DOT, None, rag_debug, usage

    if _needs_human(parsed, parsed.get("agente_destino")):
        return _handoff_message(parsed), parsed, rag_debug, usage

    if _has_message(parsed):
        return _extract_message(parsed) or DEFAULT_NO_RESPONSE_DOT, parsed, rag_debug, usage

    return raw_reply or DEFAULT_NO_RESPONSE_DOT, parsed, rag_debug, usage


def run_agent_raw(
    agent_record: dict[str, Any],
    user_prompt: str,
    context: AgentContext,
    run_async_fn: callable,
    log_path: Path | str | None = None,
) -> tuple[str | None, dict[str, Any], UsageDict | None]:
    """
    Execute agent at raw level with full model interaction.
    
    Returns:
        Tuple of (raw_response, rag_debug, usage_info)
    """
    model_name = (agent_record.get("model") or "").strip()

    if log_path:
        append_log(log_path, "agent_start", {
            "agent_name": agent_record.get("nome"),
            "user_prompt": user_prompt,
            "context_msg": context.mensagem
        })

    if not model_name:
        return None, _empty_rag_debug(agent_record), None

    try:
        api_key = get_settings().OPENAI_API_KEY
    except Exception:
        return None, _empty_rag_debug(agent_record), None

    rag_context, rag_debug = _get_rag_context(agent_record, user_prompt, run_async_fn)

    # Build system prompt
    parts = []
    bot_persona = agent_record.get("bot_persona")
    if bot_persona:
        parts.append(f"=== INSTRUÇÕES GLOBAIS (PERSONA) ===\n{bot_persona}")

    agent_prompt = (agent_record.get("system_prompt") or "").strip()
    if agent_prompt:
        parts.append(f"=== INSTRUÇÕES DO AGENTE ===\n{agent_prompt}")

    context_text = render_context(context)
    parts.append(f"=== CONTEXTO DA SESSÃO ===\n{context_text}")

    if rag_context:
        parts.append(f"=== CONTEXTO RAG ===\n{rag_context}")

    system_prompt = "\n\n".join(parts)

    # Determine result type based on role
    role = resolve_role_label(agent_record.get("papel"))
    result_type = str
    if role == AgentRole.TRIAGEM:
        result_type = RouteDecision
    elif role == AgentRole.COORDENADOR:
        result_type = CoordinatorDecision
    elif role == AgentRole.RESUMO:
        result_type = HandoffSummary
    elif role in [AgentRole.COMERCIAL, AgentRole.GUIA_UNIDADES, AgentRole.COTADOR, AgentRole.CONSULTOR_TECNICO]:
        result_type = AgentReply

    agent = Agent(
        OpenAIModel(model_name, api_key=api_key),
        system_prompt=system_prompt,
        name=agent_record.get("nome"),
        result_type=result_type,
        defer_model_check=True,
    )
    
    try:
        result = run_async_fn(agent.run(user_prompt))
    except Exception:
        return None, rag_debug, None

    usage_info = None
    if hasattr(result, "usage"):
        usage = result.usage()
        usage_info = {
            "input": usage.request_tokens or 0,
            "output": usage.response_tokens or 0,
            "total": usage.total_tokens or 0,
        }

    if hasattr(result.data, "model_dump_json"):
        raw_result = result.data.model_dump_json()
    else:
        raw_result = str(result.data or "").strip()

    if log_path:
        append_log(log_path, "agent_success", {"raw_reply": raw_result, "usage": usage_info})

    # NEW: Log to global LLM history
    log_llm_interaction(
        agent_name=agent_record.get("nome"),
        model=model_name,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response=raw_result,
        usage=usage_info
    )

    return raw_result, rag_debug, usage_info


# -----------------------------------------------------------------------------
# Text Cleanup
# -----------------------------------------------------------------------------
def clean_reply_text(text: str) -> str:
    """
    Clean agent response text by removing JSON artifacts and prefixes.
    
    This handles various formats including:
    - AgentReply prefixes
    - JSON wrappers
    - Triple quotes
    - Malformed JSON strings
    """
    if not text:
        return ""

    clean = text.strip()
    
    # Remove AgentReply prefix
    clean = re.sub(r"^(?:<)?AgentReply(?:>)?[:\s]*", "", clean, flags=re.IGNORECASE).strip()
    
    # Remove triple quotes
    clean = re.sub(r"^['\"]3\s*", "", clean)
    clean = re.sub(r"['\"]3\s*$", "", clean)
    clean = re.sub(r"^(?:<)?AgentReply(?:>)?[:\s]*", "", clean, flags=re.IGNORECASE).strip()
    clean = re.sub(r"</AgentReply>$", "", clean, flags=re.IGNORECASE).strip()
    
    if clean.startswith(":"):
        clean = clean[1:].strip()

    # Remove surrounding brackets
    if (clean.startswith("(") and clean.endswith(")")) or \
       (clean.startswith("{") and clean.endswith("}")) or \
       (clean.startswith("[") and clean.endswith("]")):
        clean = clean[1:-1].strip()

    # Remove surrounding quotes
    if (clean.startswith('"') and clean.endswith('"')) or \
       (clean.startswith("'") and clean.endswith("'")):
        clean = clean[1:-1]

    # Try to parse as JSON
    try:
        data = json.loads(clean)
    except Exception:
        data = None

    if data is None:
        try:
            data = ast.literal_eval(clean)
        except Exception:
            data = None

    if isinstance(data, dict):
        for key in ["response", "mensagem", "message", "content", "text"]:
            if key in data and isinstance(data[key], str):
                return data[key]
        for v in data.values():
            if isinstance(v, str):
                return v
    elif isinstance(data, str):
        return data

    # Aggressive prefix cleanup
    prefix_pattern = r'^\s*["\']?(?:response|resposta|mensagem|message|content|text|cliente|client|bot|atendente|assistant)["\']?\s*[:=]\s*["\']?'
    clean = re.sub(prefix_pattern, "", clean, flags=re.IGNORECASE).strip()

    # Try loose JSON pattern
    loose_json_pattern = r'["\']?(?:response|resposta|mensagem|message|content|text|cliente|client|bot|atendente|assistant)["\']?\s*[:=]\s*["\'](.+?)["\']'
    m_loose = re.search(loose_json_pattern, clean, re.IGNORECASE | re.DOTALL)
    if m_loose:
        return m_loose.group(1)

    # Try various patterns
    patterns = [
        r"(?:message|mensagem|response)\s*=\s*['\"](.+?)['\"](?:,|}|\)|$)",
        r"['\"](?:message|mensagem|response)['\"]\s*[:=]\s*['\"](.+?)['\"](?:,|}|\)|$)",
        r"AgentReply\s*\(\s*['\"](.+?)['\"]\s*\)",
        r"AgentReply\s*\{.+?['\"](?:message|mensagem|response)['\"]\s*:\s*['\"](.+?)['\"].+?\}"
    ]
    for pat in patterns:
        m = re.search(pat, clean, re.IGNORECASE | re.DOTALL)
        if m:
            return m.group(1)

    # Handle AgentReply remainder
    if clean.startswith("AgentReply"):
        first_quote = -1
        for q in ['"', "'"]:
            f = clean.find(q)
            if f != -1 and (first_quote == -1 or f < first_quote):
                first_quote = f

        if first_quote != -1:
            q_char = clean[first_quote]
            last_quote = clean.rfind(q_char)
            if last_quote > first_quote:
                return clean[first_quote + 1:last_quote]

    # Garbage filter
    if len(clean) < 5 and not any(c.isalnum() for c in clean):
        return ""

    return clean


# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------
def sum_usage(u1: UsageDict | None, u2: UsageDict | None) -> UsageDict:
    """Sum two usage dictionaries."""
    base = {"input": 0, "output": 0, "total": 0}
    if u1:
        base["input"] += u1.get("input", 0)
        base["output"] += u1.get("output", 0)
        base["total"] += u1.get("total", 0)
    if u2:
        base["input"] += u2.get("input", 0)
        base["output"] += u2.get("output", 0)
        base["total"] += u2.get("total", 0)
    return base


def extract_json(text: str) -> dict[str, Any] | None:
    """Extract JSON object from text, handling code blocks and malformed input."""
    if not text:
        return None
    
    payload = text.strip()
    
    # Handle markdown code blocks
    if payload.startswith("```"):
        payload = payload.strip("`").strip()
        if payload.lower().startswith("json"):
            payload = payload[4:].strip()
    
    # Extract JSON object
    if not (payload.startswith("{") and payload.endswith("}")):
        start = payload.find("{")
        end = payload.rfind("}")
        if start >= 0 and end > start:
            payload = payload[start:end + 1]
    
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None
    
    return data if isinstance(data, dict) else None


def _string_or_none(value: Any) -> str | None:
    """Convert value to string if not empty, otherwise None."""
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _has_message(payload: dict[str, Any]) -> bool:
    """Check if payload contains a message field."""
    return bool(_string_or_none(payload.get("mensagem")))


def _extract_message(payload: dict[str, Any]) -> str | None:
    """Extract message from payload."""
    message = _string_or_none(payload.get("mensagem")) or _string_or_none(payload.get("message"))
    if message:
        return message
    clarifier = _string_or_none(payload.get("pergunta_clareadora"))
    if clarifier:
        return clarifier
    return None


def _needs_human(payload: dict[str, Any], destination: Any) -> bool:
    """Check if response requires human escalation."""
    if payload.get("precisa_humano") is True:
        return True
    action = _string_or_none(payload.get("acao"))
    if action == "escalar_humano":
        return True
    if isinstance(destination, str) and "humano" in destination.lower():
        return True
    return False


def _handoff_message(payload: dict[str, Any]) -> str:
    """Generate human handoff message."""
    motivo = _string_or_none(payload.get("motivo_escalacao")) or _string_or_none(payload.get("motivo"))
    if motivo:
        return f"Vou encaminhar seu atendimento para um humano. Motivo: {motivo}"
    return DEFAULT_HANDOFF_MESSAGE


def _map_agents_by_role(
    linked_agents: list[dict[str, Any]],
    agents_by_id: dict[int, dict[str, Any]],
) -> dict[AgentRole, dict[str, Any]]:
    """Create mapping from agent role to agent config."""
    mapped: dict[AgentRole, dict[str, Any]] = {}
    for link in linked_agents:
        agent = agents_by_id.get(link["agent_id"])
        if not agent or not agent.get("ativo"):
            continue
        role = resolve_role_label(agent.get("papel") or agent.get("nome"))
        if role and role not in mapped:
            mapped[role] = agent
    return mapped


# -----------------------------------------------------------------------------
# Debug Helpers
# -----------------------------------------------------------------------------
def _init_debug_info(context: AgentContext, orchestrator_agent: dict[str, Any]) -> DebugDict:
    """Initialize debug info structure."""
    return {
        "context": _context_debug(context),
        "orchestrator": _agent_debug(orchestrator_agent),
        "roteador": {},
        "roteamento": {},
        "responder": {},
        "resposta": {},
        "rag": {},
    }


def _context_debug(context: AgentContext) -> dict[str, Any]:
    """Create debug representation of context."""
    return {
        "mensagem": context.mensagem,
        "canal": context.canal,
        "origem": context.origem,
        "horario_local": context.horario_local,
        "fora_horario": context.fora_horario,
        "pediu_humano": context.pediu_humano,
    }


def _agent_debug(agent_record: dict[str, Any] | None) -> dict[str, Any]:
    """Create debug representation of agent."""
    if not agent_record:
        return {}
    return {
        "id": agent_record.get("id"),
        "nome": agent_record.get("nome"),
        "papel": agent_record.get("papel"),
        "model": agent_record.get("model"),
        "versao": agent_record.get("versao"),
        "ativo": agent_record.get("ativo"),
        "rag_id": agent_record.get("rag_id"),
    }


def _summarize_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Summarize payload for debug output."""
    if not payload:
        return {}
    return {k: v for k, v in payload.items() if k not in ("mensagem", "message")}


# -----------------------------------------------------------------------------
# RAG Helpers
# -----------------------------------------------------------------------------
def _empty_rag_debug(agent_record: dict[str, Any]) -> dict[str, Any]:
    """Create empty RAG debug structure."""
    rag_id = agent_record.get("rag_id")
    rag_identificador = agent_record.get("rag_identificador")
    rag_nome = agent_record.get("rag_nome")
    rag_provedor = agent_record.get("rag_provedor")
    rag_configurado = bool(rag_identificador or rag_id)
    rag_status = "nao configurado" if not rag_configurado else "nao consultado"
    return {
        "rag_id": rag_id,
        "rag_identificador": rag_identificador,
        "rag_nome": rag_nome,
        "rag_provedor": rag_provedor,
        "rag_configurado": rag_configurado,
        "rag_consultado": False,
        "rag_status": rag_status,
        "rag_top_k": 0,
        "rag_resultados": [],
    }


def _merge_rag_debug(agent_debug: dict[str, Any], rag_debug: dict[str, Any]) -> dict[str, Any]:
    """Merge RAG debug info into agent debug."""
    if not rag_debug:
        return agent_debug
    for key, value in rag_debug.items():
        if key.startswith("rag_"):
            agent_debug[key] = value
    return agent_debug


def _get_rag_context(
    agent_record: dict[str, Any],
    user_prompt: str,
    run_async_fn: callable,
) -> tuple[str, dict[str, Any]]:
    """Get RAG context for agent."""
    rag_debug = _empty_rag_debug(agent_record)
    
    if not rag_debug["rag_configurado"]:
        return "", rag_debug
    
    rag_identifier = rag_debug.get("rag_identificador")
    if not rag_identifier:
        rag_debug["rag_status"] = "identificador do RAG nao encontrado"
        return "", rag_debug
    
    if not (user_prompt or "").strip():
        rag_debug["rag_status"] = "consulta vazia"
        return "", rag_debug

    provider = rag_debug.get("rag_provedor")
    
    if provider == RAG_PROVIDER_CHROMADB:
        try:
            top_k = 3
            results = _query_chromadb(rag_identifier, user_prompt, top_k=top_k)
        except Exception as exc:
            rag_debug["rag_status"] = f"erro ao consultar RAG: {exc}"
            return "", rag_debug

        rag_debug["rag_consultado"] = True
        rag_debug["rag_top_k"] = top_k
        rag_debug["rag_resultados"] = results
        rag_debug["rag_status"] = "ok" if results else "sem resultados"
        return _format_rag_context(results), rag_debug

    if provider == RAG_PROVIDER_OPENAI:
        rag_debug["rag_status"] = "provedor OpenAI nao suportado no playground"
        return "", rag_debug

    rag_debug["rag_status"] = "provedor nao suportado no playground"
    return "", rag_debug


def _query_chromadb(collection_name: str, query: str, top_k: int) -> list[dict[str, Any]]:
    """Query ChromaDB for relevant documents."""
    settings = get_settings()
    chroma_host = (settings.CHROMA_HOST or "").strip()
    if not chroma_host:
        raise ValueError("CHROMA_HOST nao configurado.")
    
    openai_key = (settings.OPENAI_API_KEY or "").strip()
    if not openai_key:
        raise ValueError("OPENAI_API_KEY nao configurada para embeddings.")

    host, port, ssl = _parse_chroma_host(chroma_host)
    
    try:
        import chromadb
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
    except Exception as exc:
        raise RuntimeError(f"Falha ao carregar chromadb: {exc}") from exc

    embedding_fn = OpenAIEmbeddingFunction(api_key=openai_key, model_name="text-embedding-3-small")
    client = chromadb.HttpClient(host=host, port=port, ssl=ssl)
    collection = client.get_collection(name=collection_name, embedding_function=embedding_fn)
    
    response = collection.query(
        query_texts=[query],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )
    
    documents = (response.get("documents") or [[]])[0]
    metadatas = (response.get("metadatas") or [[]])[0]
    distances = (response.get("distances") or [[]])[0]

    results = []
    for i, doc in enumerate(documents):
        meta = metadatas[i] if i < len(metadatas) else {}
        dist = distances[i] if i < len(distances) else None
        results.append({
            "content": doc,
            "metadata": meta,
            "distance": dist,
            "source": _pick_rag_source(meta),
        })
    
    return results


def _parse_chroma_host(chroma_host: str) -> tuple[str, int, bool]:
    """Parse ChromaDB host string into components."""
    from urllib.parse import urlparse
    
    parsed = urlparse(chroma_host if "://" in chroma_host else f"http://{chroma_host}")
    host = parsed.hostname or "localhost"
    port = parsed.port or 8000
    ssl = parsed.scheme == "https"
    return host, port, ssl


def _format_rag_context(results: list[dict[str, Any]]) -> str:
    """Format RAG results as context string."""
    if not results:
        return ""
    
    lines = []
    for i, result in enumerate(results, 1):
        content = result.get("content", "")
        source = result.get("source", "")
        dist = result.get("distance")
        
        header = f"[{i}]"
        if source:
            header += f" ({source})"
        if dist is not None:
            header += f" [dist: {dist:.4f}]"
        
        lines.append(f"{header}\n{content}")
    
    return "\n\n".join(lines)


def _pick_rag_source(metadata: dict[str, Any]) -> str:
    """Extract source name from RAG metadata."""
    for key in ["source", "filename", "file", "title", "name"]:
        if key in metadata and metadata[key]:
            return str(metadata[key])
    return ""
