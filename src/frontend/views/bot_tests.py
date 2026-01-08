from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import streamlit as st
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.agent_architecture import (
    AGENT_DISPLAY_NAMES,
    AgentContext,
    AgentRole,
    render_context,
    resolve_role_label,
)
from src.core.agents import list_agents
from src.core.bots import ensure_tables, list_bot_agents, list_bots
from src.core.config import get_settings
from src.core.rag_management import RAG_PROVIDER_CHROMADB, RAG_PROVIDER_OPENAI
from src.frontend.shared import page_header, render_db_status, run_async


def render() -> None:
    page_header("Testes de bots", "Simule conversas com bots cadastrados.")
    render_db_status()
    run_async(ensure_tables())

    bots_data = run_async(list_bots())
    if not bots_data:
        st.info("Nenhum bot cadastrado ainda.")
        return

    selected_bot = _render_bot_selector(bots_data)
    if not selected_bot:
        return

    agents_data = run_async(list_agents())
    agents_by_id = {agent["id"]: agent for agent in agents_data}
    linked_agents = run_async(list_bot_agents(selected_bot["id"]))
    orchestrator_link = next(
        (link for link in linked_agents if link.get("role") == "orquestrador"),
        None,
    )

    _render_bot_summary(selected_bot, linked_agents, agents_by_id, orchestrator_link)
    if orchestrator_link is None:
        st.warning("Este bot nao possui agente orquestrador. Edite o bot e selecione um.")
        return

    orchestrator_agent = agents_by_id.get(orchestrator_link["agent_id"])
    if not orchestrator_agent:
        st.error("Agente orquestrador nao encontrado. Verifique os vinculos do bot.")
        return

    _render_chat_playground(selected_bot, orchestrator_agent, linked_agents, agents_by_id)


def _render_bot_selector(bots_data: list[dict[str, Any]]) -> dict[str, Any] | None:
    options: dict[str, int] = {}
    for bot in bots_data:
        status = "Ativo" if bot.get("ativo") else "Inativo"
        versao = bot.get("versao") or "-"
        label = f"{bot.get('nome', '-')} - v{versao} ({status})"
        if label in options:
            label = f"{label} [ID {bot.get('id')}]"
        options[label] = bot["id"]

    labels = list(options.keys())
    selected_label = st.selectbox("Bot para teste", labels, index=0)
    bot_id = options.get(selected_label)
    return next((b for b in bots_data if b["id"] == bot_id), None)


def _render_bot_summary(
    bot: dict[str, Any],
    linked_agents: list[dict[str, Any]],
    agents_by_id: dict[int, dict[str, Any]],
    orchestrator_link: dict[str, Any] | None,
) -> None:
    st.subheader("Resumo do bot")
    cols = st.columns([2, 1, 1, 1])
    cols[0].write(bot.get("descricao") or "-")
    cols[1].write(f"Versao: {bot.get('versao') or '-'}")
    cols[2].write("Status: " + ("Ativo" if bot.get("ativo") else "Inativo"))
    cols[3].write(f"Agentes: {len(linked_agents)}")

    if orchestrator_link:
        orchestrator_agent = agents_by_id.get(orchestrator_link["agent_id"])
        if orchestrator_agent:
            st.info(
                "Agente orquestrador: "
                f"{orchestrator_agent.get('nome', '-')}"
                f" (v{orchestrator_agent.get('versao') or '-'})"
            )

    with st.expander("Agentes vinculados"):
        if not linked_agents:
            st.write("Nenhum agente vinculado.")
            return
        for link in linked_agents:
            agent = agents_by_id.get(link["agent_id"])
            if not agent:
                st.write(f"Agente ID {link['agent_id']} (nao encontrado)")
                continue
            role_label = "Orquestrador" if link.get("role") == "orquestrador" else "Vinculado"
            status = "Ativo" if agent.get("ativo") else "Inativo"
            st.write(
                f"{agent.get('nome', '-')}"
                f" - v{agent.get('versao') or '-'}"
                f" ({status})"
                f" [{role_label}]"
            )


def _render_chat_playground(
    bot: dict[str, Any],
    orchestrator_agent: dict[str, Any],
    linked_agents: list[dict[str, Any]],
    agents_by_id: dict[int, dict[str, Any]],
) -> None:
    st.subheader("Playground")
    st.caption("As respostas sao geradas pelo agente orquestrador selecionado no bot.")

    if not orchestrator_agent.get("ativo"):
        st.warning("O agente orquestrador esta inativo. Ative-o para testar.")

    chat_state = _get_chat_state(bot["id"])

    controls = st.columns([1, 1])
    if controls[0].button("Limpar conversa", type="secondary", use_container_width=True):
        chat_state["display"] = []
        st.rerun()

    if controls[1].button("Mostrar prompt", use_container_width=True):
        st.session_state[f"bot_prompt_{bot['id']}"] = not st.session_state.get(
            f"bot_prompt_{bot['id']}", False
        )

    debug_cols = st.columns([1.2, 1.4, 2.4])
    debug_key = f"bot_debug_{bot['id']}"
    advanced_debug_key = f"bot_debug_advanced_{bot['id']}"
    debug_enabled = debug_cols[0].checkbox("Modo Debug", key=debug_key)
    advanced_debug = debug_cols[1].checkbox("Debug Avançado", key=advanced_debug_key)
    if advanced_debug:
        if not st.session_state.get(debug_key, False):
            st.session_state[debug_key] = True
        debug_enabled = True

    if st.session_state.get(f"bot_prompt_{bot['id']}", False):
        st.code(orchestrator_agent.get("system_prompt") or "-", language="markdown")

    for message in chat_state["display"]:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant" and debug_enabled:
                _render_debug_info(message.get("debug"), advanced_debug)
            st.write(message["content"])

    user_input = st.chat_input("Digite sua mensagem para o bot")
    if not user_input:
        return

    chat_state["display"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Gerando resposta..."):
            response_text, debug_info = _run_orchestrator_reply(
                orchestrator_agent,
                linked_agents,
                agents_by_id,
                user_input,
            )
            if debug_enabled:
                _render_debug_info(debug_info, advanced_debug)
            st.write(response_text)

    chat_state["display"].append(
        {"role": "assistant", "content": response_text, "debug": debug_info}
    )


def _get_chat_state(bot_id: int) -> dict[str, Any]:
    if "bot_test_sessions" not in st.session_state:
        st.session_state.bot_test_sessions = {}
    sessions = st.session_state.bot_test_sessions
    if bot_id not in sessions:
        sessions[bot_id] = {"display": []}
    return sessions[bot_id]


def _run_orchestrator_reply(
    orchestrator_agent: dict[str, Any],
    linked_agents: list[dict[str, Any]],
    agents_by_id: dict[int, dict[str, Any]],
    user_prompt: str,
) -> tuple[str, dict[str, Any]]:
    model_name = (orchestrator_agent.get("model") or "").strip()
    if not model_name:
        return "Modelo do agente orquestrador nao configurado.", {}

    context = AgentContext(
        mensagem=user_prompt,
        canal="playground",
        origem="playground",
    )
    debug_info = _init_debug_info(context, orchestrator_agent)
    agents_by_role = _map_agents_by_role(linked_agents, agents_by_id)
    raw_reply, router_rag = _run_agent_raw(orchestrator_agent, user_prompt, context)
    debug_info["roteador"] = _merge_rag_debug(_agent_debug(orchestrator_agent), router_rag)
    if raw_reply is None:
        debug_info["responder"] = debug_info["roteador"]
        debug_info["rag"] = router_rag
        return "Erro ao gerar resposta com o agente orquestrador.", debug_info

    parsed = _extract_json(raw_reply)
    debug_info["roteamento"] = _summarize_payload(parsed)
    if parsed is None:
        debug_info["responder"] = debug_info["roteador"]
        debug_info["resposta"] = _summarize_payload(None)
        debug_info["rag"] = router_rag
        return raw_reply or "Sem resposta.", debug_info

    if _has_message(parsed):
        debug_info["responder"] = debug_info["roteador"]
        debug_info["resposta"] = _summarize_payload(parsed)
        debug_info["rag"] = router_rag
        return _extract_message(parsed) or "Sem resposta.", debug_info

    destination = parsed.get("agente_destino")
    if not destination:
        debug_info["responder"] = debug_info["roteador"]
        debug_info["resposta"] = _summarize_payload(parsed)
        debug_info["rag"] = router_rag
        return raw_reply or "Sem resposta.", debug_info

    if _needs_human(parsed, destination):
        debug_info["responder"] = debug_info["roteador"]
        debug_info["resposta"] = _summarize_payload(parsed)
        debug_info["rag"] = router_rag
        return _handoff_message(parsed), debug_info

    clarifier = _string_or_none(parsed.get("pergunta_clareadora"))
    if clarifier:
        debug_info["responder"] = debug_info["roteador"]
        debug_info["resposta"] = _summarize_payload(parsed)
        debug_info["rag"] = router_rag
        return clarifier, debug_info

    destination_role = resolve_role_label(destination)
    if destination_role is None:
        debug_info["responder"] = debug_info["roteador"]
        debug_info["resposta"] = _summarize_payload(parsed)
        debug_info["rag"] = router_rag
        return "Agente destino nao reconhecido.", debug_info

    if destination_role == AgentRole.COORDENADOR:
        coordinator = agents_by_role.get(AgentRole.COORDENADOR)
        if not coordinator:
            debug_info["responder"] = debug_info["roteador"]
            debug_info["resposta"] = _summarize_payload(parsed)
            debug_info["rag"] = router_rag
            return "Agente coordenador nao encontrado.", debug_info
        response_text, coordinator_payload, responder_agent, responder_payload, responder_rag = _run_coordinator_flow(
            coordinator, agents_by_role, user_prompt, context
        )
        debug_info["coordenador"] = _summarize_payload(coordinator_payload)
        debug_info["responder"] = _merge_rag_debug(
            _agent_debug(responder_agent or coordinator),
            responder_rag,
        )
        debug_info["resposta"] = _summarize_payload(responder_payload)
        debug_info["rag"] = responder_rag
        return response_text, debug_info

    destination_agent = agents_by_role.get(destination_role)
    if not destination_agent:
        debug_info["responder"] = debug_info["roteador"]
        debug_info["resposta"] = _summarize_payload(parsed)
        debug_info["rag"] = router_rag
        return "Agente destino nao encontrado.", debug_info
    response_text, responder_payload, responder_rag = _run_agent_reply(
        destination_agent, user_prompt, context
    )
    debug_info["responder"] = _merge_rag_debug(_agent_debug(destination_agent), responder_rag)
    debug_info["resposta"] = _summarize_payload(responder_payload)
    debug_info["rag"] = responder_rag
    return response_text, debug_info


def _run_coordinator_flow(
    coordinator_agent: dict[str, Any],
    agents_by_role: dict[AgentRole, dict[str, Any]],
    user_prompt: str,
    context: AgentContext,
) -> tuple[
    str,
    dict[str, Any] | None,
    dict[str, Any] | None,
    dict[str, Any] | None,
    dict[str, Any],
]:
    raw_reply, coordinator_rag = _run_agent_raw(coordinator_agent, user_prompt, context)
    if raw_reply is None:
        return "Erro ao gerar resposta com o agente coordenador.", None, None, None, coordinator_rag

    parsed = _extract_json(raw_reply)
    if parsed is None:
        return raw_reply or "Sem resposta.", None, coordinator_agent, None, coordinator_rag

    if _needs_human(parsed, parsed.get("agente_destino")):
        return _handoff_message(parsed), parsed, coordinator_agent, parsed, coordinator_rag

    action = _string_or_none(parsed.get("acao"))
    destination = parsed.get("agente_destino")
    if action == "redirecionar" and destination:
        destination_role = resolve_role_label(destination)
        if destination_role and destination_role in agents_by_role:
            response_text, responder_payload, responder_rag = _run_agent_reply(
                agents_by_role[destination_role], user_prompt, context
            )
            return response_text, parsed, agents_by_role[destination_role], responder_payload, responder_rag

    if _has_message(parsed):
        return _extract_message(parsed) or "Sem resposta.", parsed, coordinator_agent, parsed, coordinator_rag

    return raw_reply or "Sem resposta.", parsed, coordinator_agent, parsed, coordinator_rag


def _run_agent_reply(
    agent_record: dict[str, Any],
    user_prompt: str,
    context: AgentContext,
) -> tuple[str, dict[str, Any] | None, dict[str, Any]]:
    raw_reply, rag_debug = _run_agent_raw(agent_record, user_prompt, context)
    if raw_reply is None:
        return "Erro ao gerar resposta com o agente.", None, rag_debug

    parsed = _extract_json(raw_reply)
    if parsed is None:
        return raw_reply or "Sem resposta.", None, rag_debug

    if _needs_human(parsed, parsed.get("agente_destino")):
        return _handoff_message(parsed), parsed, rag_debug

    if _has_message(parsed):
        return _extract_message(parsed) or "Sem resposta.", parsed, rag_debug

    return raw_reply or "Sem resposta.", parsed, rag_debug


def _run_agent_raw(
    agent_record: dict[str, Any],
    user_prompt: str,
    context: AgentContext,
) -> tuple[str | None, dict[str, Any]]:
    model_name = (agent_record.get("model") or "").strip()
    if not model_name:
        return None, _empty_rag_debug(agent_record)

    try:
        api_key = get_settings().OPENAI_API_KEY
    except Exception:
        return None, _empty_rag_debug(agent_record)

    rag_context, rag_debug = _get_rag_context(agent_record, user_prompt)
    system_prompt = _compose_prompt(agent_record.get("system_prompt") or "", context)
    if rag_context:
        system_prompt = f"{system_prompt}\n\nContexto RAG:\n{rag_context}"
    agent = Agent(
        OpenAIModel(model_name, api_key=api_key),
        system_prompt=system_prompt,
        name=agent_record.get("nome"),
        result_type=str,
        defer_model_check=True,
    )
    try:
        result = run_async(agent.run(user_prompt))
    except Exception:
        return None, rag_debug

    return (result.data or "").strip(), rag_debug


def _compose_prompt(base_prompt: str, context: AgentContext) -> str:
    base = (base_prompt or "").strip()
    context_text = render_context(context)
    if not base:
        return context_text
    return f"{base}\n\nContexto do atendimento:\n{context_text}"


def _extract_json(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    payload = text.strip()
    if payload.startswith("```"):
        payload = payload.strip("`").strip()
        if payload.lower().startswith("json"):
            payload = payload[4:].strip()
    if not (payload.startswith("{") and payload.endswith("}")):
        start = payload.find("{")
        end = payload.rfind("}")
        if start >= 0 and end > start:
            payload = payload[start : end + 1]
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _has_message(payload: dict[str, Any]) -> bool:
    return bool(_string_or_none(payload.get("mensagem")))


def _extract_message(payload: dict[str, Any]) -> str | None:
    message = _string_or_none(payload.get("mensagem"))
    if message:
        return message
    clarifier = _string_or_none(payload.get("pergunta_clareadora"))
    if clarifier:
        return clarifier
    return None


def _needs_human(payload: dict[str, Any], destination: Any) -> bool:
    if payload.get("precisa_humano") is True:
        return True
    action = _string_or_none(payload.get("acao"))
    if action == "escalar_humano":
        return True
    if isinstance(destination, str) and "humano" in destination.lower():
        return True
    return False


def _handoff_message(payload: dict[str, Any]) -> str:
    motivo = _string_or_none(payload.get("motivo_escalacao")) or _string_or_none(payload.get("motivo"))
    if motivo:
        return f"Vou encaminhar seu atendimento para um humano. Motivo: {motivo}"
    return "Vou encaminhar seu atendimento para um humano."


def _map_agents_by_role(
    linked_agents: list[dict[str, Any]],
    agents_by_id: dict[int, dict[str, Any]],
) -> dict[AgentRole, dict[str, Any]]:
    mapped: dict[AgentRole, dict[str, Any]] = {}
    for link in linked_agents:
        agent = agents_by_id.get(link["agent_id"])
        if not agent or not agent.get("ativo"):
            continue
        role = resolve_role_label(agent.get("papel") or agent.get("nome"))
        if role and role not in mapped:
            mapped[role] = agent
    return mapped


def _empty_rag_debug(agent_record: dict[str, Any]) -> dict[str, Any]:
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
    if not rag_debug:
        return agent_debug
    for key, value in rag_debug.items():
        if key.startswith("rag_"):
            agent_debug[key] = value
    return agent_debug


def _get_rag_context(agent_record: dict[str, Any], user_prompt: str) -> tuple[str, dict[str, Any]]:
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
    results: list[dict[str, Any]] = []
    for idx, doc in enumerate(documents):
        results.append(
            {
                "documento": doc,
                "metadados": metadatas[idx] if idx < len(metadatas) else None,
                "distancia": distances[idx] if idx < len(distances) else None,
            }
        )
    return results


def _parse_chroma_host(chroma_host: str) -> tuple[str, int, bool]:
    parsed = urlparse(chroma_host)
    ssl = parsed.scheme == "https"
    if parsed.scheme:
        host = parsed.hostname or ""
        port = parsed.port or 8000
    else:
        if ":" in chroma_host:
            host_part, port_part = chroma_host.split(":", 1)
            host = host_part.strip()
            port = int(port_part.strip() or 8000)
        else:
            host = chroma_host.strip()
            port = 8000
    if not host:
        raise ValueError("CHROMA_HOST invalido.")
    return host, port, ssl


def _format_rag_context(results: list[dict[str, Any]]) -> str:
    if not results:
        return ""
    chunks = []
    for idx, item in enumerate(results, start=1):
        document = _truncate_text(str(item.get("documento") or ""), 600)
        metadata = item.get("metadados") or {}
        source = _pick_rag_source(metadata)
        header = f"[{idx}]"
        if source:
            header = f"{header} Fonte: {source}"
        chunks.append(f"{header}\n{document}")
    return "\n\n".join(chunks)


def _truncate_text(text: str, limit: int) -> str:
    cleaned = (text or "").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 3)] + "..."


def _pick_rag_source(metadata: dict[str, Any]) -> str:
    for key in ("source", "arquivo", "file", "url", "path", "titulo", "title"):
        value = metadata.get(key)
        if value:
            return str(value)
    return ""


def _init_debug_info(context: AgentContext, orchestrator_agent: dict[str, Any]) -> dict[str, Any]:
    return {
        "context": _context_debug(context),
        "roteador": _agent_debug(orchestrator_agent),
        "roteamento": None,
        "coordenador": None,
        "responder": None,
        "resposta": None,
        "rag": None,
    }


def _context_debug(context: AgentContext) -> dict[str, Any]:
    return {
        "canal": context.canal,
        "origem": context.origem,
        "fora_horario": context.fora_horario,
        "pediu_humano": context.pediu_humano,
        "nomes_citados": context.nomes_citados,
    }


def _agent_debug(agent_record: dict[str, Any] | None) -> dict[str, Any]:
    if not agent_record:
        return {}
    role = resolve_role_label(agent_record.get("papel") or agent_record.get("nome"))
    rag_nome = agent_record.get("rag_nome")
    rag_identificador = agent_record.get("rag_identificador")
    rag_provedor = agent_record.get("rag_provedor")
    rag_id = agent_record.get("rag_id")
    rag_configurado = bool(rag_identificador or rag_id)
    rag_status = "nao configurado" if not rag_configurado else "nao consultado"
    rag_consultado = False
    return {
        "nome": agent_record.get("nome"),
        "papel": role.value if role else (agent_record.get("papel") or ""),
        "versao": agent_record.get("versao"),
        "modelo": agent_record.get("model"),
        "rag_nome": rag_nome,
        "rag_identificador": rag_identificador,
        "rag_provedor": rag_provedor,
        "rag_id": rag_id,
        "rag_configurado": rag_configurado,
        "rag_consultado": rag_consultado,
        "rag_status": rag_status,
    }


def _summarize_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {"formato": "texto_livre"}
    return {
        "acao": _string_or_none(payload.get("acao")),
        "agente_destino": _string_or_none(payload.get("agente_destino")),
        "intencao": _string_or_none(payload.get("intencao")),
        "motivo": _string_or_none(payload.get("motivo"))
        or _string_or_none(payload.get("motivo_escalacao")),
        "pergunta_clareadora": _string_or_none(payload.get("pergunta_clareadora")),
        "precisa_humano": payload.get("precisa_humano"),
        "dados_faltantes": payload.get("dados_faltantes"),
        "tags": payload.get("tags"),
        "formato": "contrato",
    }


def _render_debug_info(debug_info: dict[str, Any] | None, advanced: bool) -> None:
    if not debug_info:
        st.caption("Agente: -")
        return
    responder = debug_info.get("responder") or debug_info.get("roteador") or {}
    agent_label = _format_agent_label(responder)
    st.caption(f"Agente: {agent_label}")
    if not advanced:
        return

    for line in _build_debug_lines(debug_info):
        st.caption(line)

    _render_rag_details(debug_info.get("rag"))


def _format_agent_label(agent_info: dict[str, Any]) -> str:
    nome = (agent_info.get("nome") or "-").strip()
    role = resolve_role_label(agent_info.get("papel"))
    if role:
        role_label = AGENT_DISPLAY_NAMES.get(role, role.value)
        return f"{nome} ({role_label})"
    return nome


def _build_debug_lines(debug_info: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    route = debug_info.get("roteamento") or {}
    coordinator = debug_info.get("coordenador") or {}
    reply = debug_info.get("resposta") or {}
    context = debug_info.get("context") or {}
    responder = debug_info.get("responder") or {}

    reason = _string_or_none(reply.get("motivo")) or _string_or_none(coordinator.get("motivo"))
    if not reason:
        reason = _string_or_none(route.get("motivo"))
    if reason:
        lines.append(f"Resumo da decisao: {reason}")

    routing_bits = []
    route_dest = _string_or_none(route.get("agente_destino"))
    if route_dest:
        routing_bits.append(f"destino={route_dest}")
    route_intent = _string_or_none(route.get("intencao"))
    if route_intent:
        routing_bits.append(f"intencao={route_intent}")
    if routing_bits:
        lines.append("Roteamento: " + ", ".join(routing_bits))

    coord_action = _string_or_none(coordinator.get("acao"))
    if coord_action:
        coord_dest = _string_or_none(coordinator.get("agente_destino"))
        label = f"Coordenador: acao={coord_action}"
        if coord_dest:
            label += f", destino={coord_dest}"
        lines.append(label)

    reply_action = _string_or_none(reply.get("acao"))
    if reply_action:
        lines.append(f"Resposta final: acao={reply_action}")
    elif reply.get("formato") == "texto_livre":
        lines.append("Resposta final: texto livre")

    precisa_humano = reply.get("precisa_humano")
    if precisa_humano is None:
        precisa_humano = coordinator.get("precisa_humano")
    if precisa_humano is None:
        precisa_humano = route.get("precisa_humano")
    if precisa_humano is not None:
        lines.append(f"Precisa humano: {'sim' if precisa_humano else 'nao'}")

    dados = reply.get("dados_faltantes") or coordinator.get("dados_faltantes") or route.get("dados_faltantes")
    if isinstance(dados, list) and dados:
        lines.append("Dados faltantes: " + ", ".join(str(item) for item in dados))

    rag_label = _format_rag_label(responder)
    lines.append(rag_label)

    context_label = _format_context_label(context)
    if context_label:
        lines.append(context_label)

    return lines


def _render_rag_details(rag_info: dict[str, Any] | None) -> None:
    if not rag_info:
        return
    with st.expander("Detalhes do RAG"):
        if not rag_info.get("rag_configurado"):
            st.caption("Nenhum RAG configurado para este agente.")
            return
        rag_identifier = rag_info.get("rag_identificador") or rag_info.get("rag_nome")
        if rag_identifier:
            st.caption(f"Colecao: {rag_identifier}")
        if not rag_info.get("rag_consultado"):
            status = rag_info.get("rag_status") or "nao consultado"
            st.caption(f"RAG nao consultado: {status}")
            return

        status = rag_info.get("rag_status")
        if status:
            st.caption(f"Status da consulta: {status}")

        results = rag_info.get("rag_resultados") or []
        if not results:
            st.caption("Consulta RAG sem resultados.")
            return
        top_k = rag_info.get("rag_top_k") or len(results)
        st.caption(f"Top K: {top_k}")

        for idx, item in enumerate(results, start=1):
            metadata = item.get("metadados") or {}
            source = _pick_rag_source(metadata)
            distance = _format_distance(item.get("distancia"))
            title = f"{idx}."
            if source:
                title += f" Fonte: {source}"
            if distance:
                title += f" • score: {distance}"
            st.markdown(f"**{title}**")
            snippet = _truncate_text(str(item.get("documento") or ""), 240)
            st.caption(snippet or "-")


def _format_distance(value: Any) -> str | None:
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return None


def _format_rag_label(responder: dict[str, Any]) -> str:
    rag_nome = responder.get("rag_nome")
    rag_provedor = responder.get("rag_provedor")
    rag_status = responder.get("rag_status")
    rag_consultado = responder.get("rag_consultado")
    if rag_nome:
        provider = f" ({rag_provedor})" if rag_provedor else ""
        consultado_label = "sim" if rag_consultado else "nao"
        if rag_status:
            return f"RAG configurado: {rag_nome}{provider} • consultado: {consultado_label} ({rag_status})"
        return f"RAG configurado: {rag_nome}{provider} • consultado: {consultado_label}"
    return "RAG configurado: nao"


def _format_context_label(context: dict[str, Any]) -> str:
    canal = _string_or_none(context.get("canal"))
    origem = _string_or_none(context.get("origem"))
    fora_horario = context.get("fora_horario")
    pediu_humano = context.get("pediu_humano")
    nomes = context.get("nomes_citados") or []

    parts = []
    if canal:
        parts.append(f"canal={canal}")
    if origem:
        parts.append(f"origem={origem}")
    if fora_horario is not None:
        parts.append(f"fora_horario={'sim' if fora_horario else 'nao'}")
    parts.append(f"pediu_humano={'sim' if pediu_humano else 'nao'}")
    if nomes:
        parts.append(f"nomes_citados={', '.join(nomes)}")
    if not parts:
        return ""
    return "Variaveis: " + ", ".join(parts)


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
