from __future__ import annotations

import json
import re
import ast
import sys
import time
from datetime import datetime
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
    AgentReply,
    RouteDecision,
    CoordinatorDecision,
    HandoffSummary,
)
from src.core.agents import list_agents, update_agent, create_agent
from src.core.agent_architecture import AGENT_SYSTEM_PROMPTS
from src.core.bots import ensure_tables, list_bot_agents, list_bots
from src.core.config import get_settings
from src.core.rag_management import RAG_PROVIDER_CHROMADB, RAG_PROVIDER_OPENAI, get_rag_by_id
import unicodedata
from src.frontend.shared import page_header, render_db_status, run_async, render_debug_panel
from src.core.debug_logger import create_log_session, append_log, log_llm_interaction

# NEW: Import shared modules
from src.core.constants import (
    DEFAULT_NO_RESPONSE,
    DEFAULT_NO_RESPONSE_DOT,
    MAX_SAFETY_TURNS,
    RAG_DATA_DIR,
)
from src.core.orchestration import (
    run_orchestrator_reply as _shared_run_orchestrator_reply,
    run_agent_raw as _shared_run_agent_raw,
    run_agent_reply as _shared_run_agent_reply,
    clean_reply_text as _shared_clean_reply_text,
    extract_json as _shared_extract_json,
    sum_usage as _shared_sum_usage,
)
from src.core.rag_utils import resolve_rag_filename as _shared_resolve_rag_filename



def _resolve_rag_filename(agent: dict[str, Any]) -> Path | None:
    """
    Resolve o nome do arquivo RAG local baseado no RAG associado ao agente.
    Convenção: RAG-{nome_normalizado}.md de acordo com o nome do RAG no banco.
    Fallback: Se for o cliente simulado padrão e não achar pelo nome, tenta o padrão antigo.
    """
    rag_id = agent.get("rag_id")
    candidate_rag_file = None

    if rag_id:
        try:
            # Fetch RAG details from DB
            rag = run_async(get_rag_by_id(rag_id))
            if rag:
                nome = rag.get("nome", "")
                if nome:
                    normalized = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii").lower()
                    slug = normalized.replace(" ", "-")
                    
                    
                    # 1. RAG-{slug}.md
                    c1 = PROJECT_ROOT / "data/rag_files" / f"RAG-{slug}.md"
                    if c1.exists():
                        candidate_rag_file = c1
                    
                    # 2. Exact name
                    if not candidate_rag_file:
                        c2 = PROJECT_ROOT / "data/rag_files" / nome
                        if c2.exists():
                            candidate_rag_file = c2

        except Exception as e:
            print(f"Erro resolvendo arquivo RAG (DB): {e}")
            # st.warning(f"Aviso: Não foi possível resolver RAG pelo banco de dados: {e}")

    # Fallback Logic: Always run if no candidate found yet
    if not candidate_rag_file:
        role = resolve_role_label(agent.get("papel"))
        if role == AgentRole.CLIENTE_SIMULADO_PADRAO:
             legacy = PROJECT_ROOT / "data/rag_files" / "RAG-cliente-conversas-reais.md"
             if legacy.exists():
                 candidate_rag_file = legacy

    return candidate_rag_file


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

    # DEBUG: Check scenario state
    if st.session_state.get("bot_test_auto_running"):
        scenario = st.session_state.get("bot_test_auto_scenario")
        print(f"DEBUG: Render Loop - Scenario in ID: {scenario}")

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

    # TABS STRUCTURE
    tab_manual, tab_auto = st.tabs(["Testes Manuais", "Testes Automáticos"])

    with tab_manual:
        _render_chat_playground(selected_bot, orchestrator_agent, linked_agents, agents_by_id)

    with tab_auto:
        _render_auto_simulation(selected_bot, orchestrator_agent, linked_agents, agents_by_id)


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
    st.subheader("Playground Manual")
    st.caption("As respostas sao geradas pelo agente orquestrador selecionado no bot.")

    if not orchestrator_agent.get("ativo"):
        st.warning("O agente orquestrador esta inativo. Ative-o para testar.")

    chat_state = _get_chat_state(bot["id"])
    if "total_tokens" not in chat_state:
        chat_state["total_tokens"] = {"input": 0, "output": 0, "total": 0}

    controls = st.columns([1, 1])
    if controls[0].button("Limpar conversa", type="secondary", use_container_width=True, key=f"clr_manual_{bot['id']}"):
        chat_state["display"] = []
        chat_state["total_tokens"] = {"input": 0, "output": 0, "total": 0}
        st.rerun()

    if controls[1].button("Mostrar prompt", use_container_width=True, key=f"pmt_manual_{bot['id']}"):
        st.session_state[f"bot_prompt_{bot['id']}"] = not st.session_state.get(
            f"bot_prompt_{bot['id']}", False
        )

    debug_cols = st.columns([1.2, 1.4, 1.4, 2])
    debug_key = f"bot_debug_{bot['id']}"
    advanced_debug_key = f"bot_debug_advanced_{bot['id']}"
    tokens_key = f"bot_tokens_{bot['id']}"

    debug_enabled = debug_cols[0].checkbox("Modo Debug", key=debug_key)
    advanced_debug = debug_cols[1].checkbox("Debug Avançado", key=advanced_debug_key)
    tokens_enabled = debug_cols[2].checkbox("Mostrar Tokens", key=tokens_key)

    # Debug Log Checkbox (Manual Mode) -> Moved to bottom standarized panel
    log_path = st.session_state.get("debug_log_path_tests_manual")

    is_debug_active = debug_enabled or advanced_debug

    if tokens_enabled:
        total = chat_state["total_tokens"]
        
        models_html = ""
        if "models" in total and total["models"]:
            models_rows = []
            for model_name, usage in total["models"].items():
                models_rows.append(
                    f"""
                    <div style="font-size: 0.85em; color: #555; margin-top: 4px;">
                        <em>{model_name}</em>: 
                        In: {usage['input']} | Out: {usage['output']} | Total: {usage['total']}
                    </div>
                    """
                )
            models_html = "".join(models_rows)

        st.markdown(
            f"""
            <div style="
                background-color: #f0f2f6;
                padding: 10px;
                border-radius: 5px;
                margin-bottom: 10px;
                font-size: 0.9em;
                text-align: center;
            ">
                <div style="
                    display: flex;
                    gap: 15px;
                    justify-content: center;
                    font-weight: 600;
                ">
                    <strong>Total acumulado:</strong>
                    <span>Entrada: {total['input']}</span>
                    <span>Saída: {total['output']}</span>
                    <span>Total: {total['total']}</span>
                </div>
                {models_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

    if st.session_state.get(f"bot_prompt_{bot['id']}", False):
        st.code(orchestrator_agent.get("system_prompt") or "-", language="markdown")

    for message in chat_state["display"]:
        role_label = None
        if message["role"] == "assistant":
            agent_name = message.get("agent_name")
            role_label = f"🤖 Bot ({bot.get('nome','Bot')})" 
            if agent_name:
                role_label += f" - {agent_name}"
            
        with st.chat_message(message["role"]):
            if role_label:
                st.caption(role_label)
            if message["role"] == "assistant":
                if is_debug_active:
                    _render_debug_info(message.get("debug"), advanced_debug)
                if tokens_enabled and message.get("usage"):
                    usage = message["usage"]
                    model_label = f" ({usage.get('model')})" if usage.get("model") else ""
                    st.caption(
                        f"Tokens{model_label}: In: {usage.get('input', 0)} | "
                        f"Out: {usage.get('output', 0)} | "
                        f"Total: {usage.get('total', 0)}"
                    )
            st.write(message["content"])

    user_input = st.chat_input("Digite sua mensagem para o bot")
    
    # Debug Panel (Standardized) - Placed before chat input logic so it always renders
    render_debug_panel(f"tests_manual_{bot['id']}")

    if not user_input:
        return

    chat_state["display"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Gerando resposta..."):
            # Inject Bot Persona
            orch_agent_copy = orchestrator_agent.copy()
            if bot.get("persona"):
                orch_agent_copy["bot_persona"] = bot.get("persona")

            response_text, debug_info, usage_info = _run_orchestrator_reply(
                orch_agent_copy,
                linked_agents,
                agents_by_id,
                user_input,
                log_path=log_path,
            )
            
            if response_text:
                response_text = _clean_reply_text(response_text)
            if not response_text:
                response_text = DEFAULT_NO_RESPONSE
            
            if usage_info:
                chat_state["total_tokens"] = _sum_usage(chat_state["total_tokens"], usage_info)

            if is_debug_active:
                _render_debug_info(debug_info, advanced_debug)
            
            if tokens_enabled and usage_info:
                usage = usage_info
                model_label = f" ({usage.get('model')})" if usage.get("model") else ""
                st.caption(
                    f"Tokens{model_label}: In: {usage.get('input', 0)} | "
                    f"Out: {usage.get('output', 0)} | "
                    f"Total: {usage.get('total', 0)}"
                )
                
            st.write(response_text)

    chat_state["display"].append(
        {
            "role": "assistant",
            "content": response_text,
            "debug": debug_info,
            "usage": usage_info,
            "agent_name": debug_info.get("responder", {}).get("nome") if debug_info else None,
        }
    )
    st.rerun()


# -----------------------------------------------------------------------------
# Auto Simulation Helper Functions (Extracted for Reduced Complexity)
# -----------------------------------------------------------------------------

def _get_valid_client_agents(
    agents_by_id: dict[int, dict[str, Any]], 
    bot_id: int
) -> dict[str, dict[str, Any]]:
    """Get valid client agents for simulation."""
    valid_clients = []
    for a in agents_by_id.values():
        role_val = a.get("papel")
        if a['id'] != bot_id:
            if role_val == AgentRole.CLIENTE_SIMULADO_PADRAO or "simulado" in a["nome"].lower():
                valid_clients.append(a)
    
    return {f"{a['nome']} ({a['papel']})": a for a in valid_clients if a['ativo']}


def _init_simulation_session_state() -> None:
    """Initialize session state for auto simulation."""
    if "bot_test_auto_running" not in st.session_state:
        st.session_state.bot_test_auto_running = False
    if "bot_test_auto_transcripts" not in st.session_state:
        st.session_state.bot_test_auto_transcripts = []
    if "bot_test_auto_stats" not in st.session_state:
        st.session_state.bot_test_auto_stats = {"total_tokens": {"input": 0, "output": 0, "total": 0}}


def _reset_simulation_state(initial_scenario: str | None = None) -> None:
    """Reset simulation state for a new run."""
    for key in ["bot_test_auto_transcripts", "bot_test_auto_scenario", 
                "bot_test_auto_running", "bot_test_auto_stats", 
                "bot_test_auto_next_turn", "bot_test_auto_last_bot_msg"]:
        if key in st.session_state:
            del st.session_state[key]

    st.session_state.bot_test_auto_running = True
    st.session_state.bot_test_auto_transcripts = []
    st.session_state.bot_test_auto_stats = {"total_tokens": {"input": 0, "output": 0, "total": 0}}
    st.session_state.bot_test_auto_next_turn = "client"
    st.session_state.bot_test_auto_last_bot_msg = "Olá, sou o assistente virtual."


def _get_random_rag_phrase(client_agent: dict[str, Any]) -> str | None:
    """Get a random phrase from the client's RAG file."""
    import random
    rag_file = _resolve_rag_filename(client_agent)
    if not rag_file or not rag_file.exists():
        return None
    try:
        lines = rag_file.read_text(encoding="utf-8").splitlines()
        valid_phrases = [l.strip() for l in lines if l.strip() and not l.strip().startswith(("#", "*", "-"))]
        return random.choice(valid_phrases) if valid_phrases else None
    except Exception:
        return None


def _is_rag_client_agent(client_agent: dict[str, Any]) -> bool:
    """Check if client agent uses RAG for phrases."""
    role = resolve_role_label(client_agent.get("papel"))
    return (role == AgentRole.CLIENTE_SIMULADO_PADRAO) or ("Conversas Reais" in client_agent.get("nome", ""))


def _render_simulation_chat(
    bot: dict[str, Any],
    client_agent: dict[str, Any],
    is_debug_active: bool,
    advanced_debug: bool,
    tokens_enabled: bool,
) -> None:
    """Render the simulation chat history."""
    chat_container = st.container(height=400)
    for msg in st.session_state.bot_test_auto_transcripts:
        if msg['role'] == 'assistant':
            agent_suffix = f" - {msg.get('agent_name')}" if msg.get("agent_name") else ""
            role_label = f"🤖 Bot ({bot['nome']}{agent_suffix})"
            avatar = "🤖"
        else:
            role_label = f"👤 Cliente ({client_agent['nome']})"
            avatar = "👤"

        with chat_container.chat_message(msg['role'], avatar=avatar):
            st.caption(role_label)
            if is_debug_active and msg.get("debug"):
                _render_debug_info(msg["debug"], advanced_debug)
            st.write(msg['content'])
            if tokens_enabled and msg.get('usage'):
                u = msg['usage']
                st.caption(f"Tokens: In {u['input']} / Out {u['output']} / Total {u['total']}")


def _check_simulation_termination() -> bool:
    """Check if simulation should terminate. Returns True if terminated."""
    # Check safety limit
    interaction_count = len([m for m in st.session_state.bot_test_auto_transcripts if m['role'] == 'assistant'])
    if interaction_count >= MAX_SAFETY_TURNS:
        st.warning(f"Simulação pausada por segurança ({MAX_SAFETY_TURNS} interações).")
        st.session_state.bot_test_auto_running = False
        return True

    # Check termination phrase
    if st.session_state.bot_test_auto_transcripts:
        last_msg = st.session_state.bot_test_auto_transcripts[-1]
        if last_msg["role"] == "user":
            content = last_msg["content"].upper()
            if "TCHAU" in content and "OBRIGADO" in content:
                st.success("Simulação concluída! O cliente encerrou a conversa.")
                st.session_state.bot_test_auto_running = False
                st.balloons()
                return True
    return False


def _render_auto_simulation(bot: dict[str, Any], orchestrator_agent: dict[str, Any], linked_agents: list[dict[str, Any]], agents_by_id: dict[int, dict[str, Any]]):
    st.subheader("Playground Automático")
    st.caption("Simulação autônoma entre um Agente Cliente e o Bot selecionado.")

    # Setup agents
    all_agents = agents_by_id.values()
    valid_clients = []
    for a in all_agents:
         role_val = a.get("papel")
         # Only allow agents that are NOT the bot itself, or specific roles
         if a['id'] != bot['id'] and (role_val == AgentRole.CLIENTE_SIMULADO_PADRAO or "simulado" in a["nome"].lower()): 
             valid_clients.append(a)
             
    client_options = {f"{a['nome']} ({a['papel']})": a for a in valid_clients if a['ativo']}
    default_client_idx = 0
    for idx, label in enumerate(client_options.keys()):
        if "Cliente Simulado" in label:
            default_client_idx = idx
            break
            
    # --- Client Selection (Restored) ---
    selected_client = None
    if client_options:
        selected_client_label = st.columns([1,1])[0].selectbox("Agente Cliente", list(client_options.keys()), index=default_client_idx, key="auto_client_sel")
        selected_client = client_options[selected_client_label]
    else:
        st.columns([1,1])[0].selectbox("Agente Cliente", [], key="auto_client_sel")

    col_setup = st.columns([1, 1, 1]) # Re-instantiate setup columns slightly differently as we used one above temporarily
    # Fix layout for inputs below...
    
    # min_interactions removed as per user request
    
    initial_scenario = col_setup[1].text_input("Contexto Inicial / Cenário (Opcional)", placeholder="Ex: Pergunte sobre preço de pneu para Corolla 2020.", key="auto_scenario_input")

    # State Init for Auto Mode
    if "bot_test_auto_running" not in st.session_state:
        st.session_state.bot_test_auto_running = False
    if "bot_test_auto_transcripts" not in st.session_state:
        st.session_state.bot_test_auto_transcripts = []
    if "bot_test_auto_stats" not in st.session_state:
        st.session_state.bot_test_auto_stats = {"total_tokens": {"input": 0, "output": 0, "total": 0}}

    # Controls - Simulation
    sim_controls = st.columns([1, 1])
    start_btn = sim_controls[0].button("Iniciar Simulação", type="primary", disabled=st.session_state.bot_test_auto_running, use_container_width=True, key="auto_start")
    stop_btn = sim_controls[1].button("Parar", type="secondary", disabled=not st.session_state.bot_test_auto_running, use_container_width=True, key="auto_stop")

    st.divider()

    # Controls - Playground Display
    pg_controls = st.columns([1, 1])
    if pg_controls[0].button("Limpar conversa", type="secondary", disabled=st.session_state.bot_test_auto_running, use_container_width=True, key="auto_clear"):
        st.session_state.bot_test_auto_transcripts = []
        st.session_state.bot_test_auto_stats =  {"total_tokens": {"input": 0, "output": 0, "total": 0}}
        st.rerun()

    if pg_controls[1].button("Mostrar prompt", use_container_width=True, key=f"auto_pmt_{bot['id']}"):
         st.session_state[f"auto_prompt_vis_{bot['id']}"] = not st.session_state.get(f"auto_prompt_vis_{bot['id']}", False)

    # Checkboxes for Debug
    debug_cols = st.columns([1.2, 1.4, 1.4, 2])
    debug_key = f"auto_debug_{bot['id']}"
    advanced_debug_key = f"auto_debug_adv_{bot['id']}"
    tokens_key = f"auto_tokens_{bot['id']}"

    debug_enabled = debug_cols[0].checkbox("Modo Debug", key=debug_key)
    advanced_debug = debug_cols[1].checkbox("Debug Avançado", key=advanced_debug_key)
    tokens_enabled = debug_cols[2].checkbox("Mostrar Tokens", key=tokens_key)

    is_debug_active = debug_enabled or advanced_debug

    # Debug Panel (Standardized)
    render_debug_panel(f"tests_auto_{bot['id']}")

    if st.session_state.get(f"auto_prompt_vis_{bot['id']}", False):
        prompt_content = selected_client.get("system_prompt") if selected_client else "Nenhum cliente selecionado."
        st.code(prompt_content or "-", language="markdown")

    if start_btn and selected_client:
        # Reset state extensively
        for key in ["bot_test_auto_transcripts", "bot_test_auto_scenario", "bot_test_auto_running", "bot_test_auto_stats", "bot_test_auto_next_turn", "bot_test_auto_last_bot_msg"]:
            if key in st.session_state:
                del st.session_state[key]
                
        st.session_state.bot_test_auto_running = True
        st.session_state.bot_test_auto_transcripts = []
        st.session_state.bot_test_auto_stats = {"total_tokens": {"input": 0, "output": 0, "total": 0}}
        st.session_state.bot_test_auto_next_turn = "client"
        st.session_state.bot_test_auto_last_bot_msg = "Olá, sou o assistente virtual."

        # Random phrase logic for Sim Client
        scenario_to_use = initial_scenario
        role = resolve_role_label(selected_client.get("papel"))
        
        # Robust check: Enum OR Name string match
        is_rag_agent = (role == AgentRole.CLIENTE_SIMULADO_PADRAO) or ("Conversas Reais" in selected_client.get("nome", ""))
        
        # DEBUG LOGGING (PERSISTENT)
        debug_log = [f"Start Sim: Role={role}, Name={selected_client.get('nome')}, IsRAG={is_rag_agent}"]
        
        if not scenario_to_use and is_rag_agent:
            import random
            
            rag_file = _resolve_rag_filename(selected_client)
            if rag_file:
                 debug_log.append(f"RAG File Resolved: {rag_file}")
            else:
                 debug_log.append("RAG File NOT Resolved.")
            
            if rag_file and rag_file.exists():
                try:
                    lines = rag_file.read_text(encoding="utf-8").splitlines()
                    # Filter: ignore empty lines and markdown headers/comments
                    valid_phrases = [
                        l.strip() for l in lines 
                        if l.strip() and not l.strip().startswith(("#", "*", "-"))
                    ]
                    if valid_phrases:
                        scenario_to_use = random.choice(valid_phrases)
                        debug_log.append(f"Phrase Selected: {scenario_to_use}")
                    else:
                        debug_log.append("Valid Phrases List is Empty!")
                except Exception as e:
                    debug_log.append(f"Exception Reading File: {e}")
            else:
                debug_log.append("RAG File Does Not Exist on Disk.")

        st.session_state.rag_debug_log = debug_log # Save to session
        st.session_state.bot_test_auto_scenario = scenario_to_use
        
        # Force Injection of First Turn
        if scenario_to_use:
            st.session_state.bot_test_auto_transcripts.append({
                "role": "user",
                "content": scenario_to_use,
                "usage": {"input": 0, "output": 0, "total": 0},
                "debug": {"source": "direct_scenario_injection"}
            })
            st.session_state.bot_test_auto_next_turn = "bot"
        else:
            st.session_state.bot_test_auto_next_turn = "client"

        st.rerun()

# ... existing code ...

    # Injected Logic: Force usage of phrases from local RAG file
    # Uses dynamic resolution based on agent's RAG


    if stop_btn:
        st.session_state.bot_test_auto_running = False
        st.rerun()

    # --- Live Feed ---
    
    stats = st.session_state.bot_test_auto_stats["total_tokens"]
    
    if tokens_enabled:
        st.markdown(
            f"""
            <div style="background-color: #f0f2f6; padding: 10px; border-radius: 5px; text-align: center; font-size: 0.9em; margin-bottom: 20px;">
                <strong>Total acumulado:</strong> 
                Entrada: {stats['input']} | Saída: {stats['output']} | <strong>Total: {stats['total']}</strong>
            </div>
            """,
            unsafe_allow_html=True
        )

    chat_container = st.container(height=400)
    for msg in st.session_state.bot_test_auto_transcripts:
        if msg['role'] == 'assistant':
             agent_suffix = f" - {msg.get('agent_name')}" if msg.get("agent_name") else ""
             role_label = f"🤖 Bot ({bot['nome']}{agent_suffix})"
             avatar = "🤖"
        else:
             role_label = f"👤 Cliente ({selected_client['nome']})"
             avatar = "👤"

        with chat_container.chat_message(msg['role'], avatar=avatar):
            st.caption(role_label)
            if is_debug_active and msg.get("debug"):
                _render_debug_info(msg["debug"], advanced_debug)
            
            st.write(msg['content'])
            
            if tokens_enabled and msg.get('usage'):
                u = msg['usage']
                st.caption(f"Tokens: In {u['input']} / Out {u['output']} / Total {u['total']}")

    # --- Execution Loop ---
    if st.session_state.bot_test_auto_running:
        interaction_count = len([m for m in st.session_state.bot_test_auto_transcripts if m['role'] == 'assistant'])
        
    if st.session_state.bot_test_auto_running:
        if st.session_state.get("rag_debug_log"):
            with st.expander("Debug Initialization Log", expanded=False):
                st.write(st.session_state.rag_debug_log)

        # Limitador de segurança
        MAX_SAFETY_TURNS = 25
        if interaction_count >= MAX_SAFETY_TURNS:
            st.warning(f"Simulação pausada por segurança ({MAX_SAFETY_TURNS} interações).")
            st.session_state.bot_test_auto_running = False
            st.rerun()
            return
            
        # Check termination phrase in last message
        if st.session_state.bot_test_auto_transcripts:
            last_msg = st.session_state.bot_test_auto_transcripts[-1]
            if last_msg["role"] == "user": # Client termination
                 content = last_msg["content"].upper()
                 if "TCHAU" in content and "OBRIGADO" in content:
                     st.success("Simulação concluída! O cliente encerrou a conversa.")
                     st.session_state.bot_test_auto_running = False
                     st.balloons()
                     st.rerun()
                     return

        with st.spinner("Simulando..."):
            # Turn Logic
            if st.session_state.bot_test_auto_next_turn == "client":
                last_bot_msg = st.session_state.bot_test_auto_last_bot_msg
                current_transcript_len = len(st.session_state.bot_test_auto_transcripts)
                scenario = st.session_state.get("bot_test_auto_scenario")
                
                # Robust RAG Injection Strategy
                # If first turn, force RAG phrase for Simulated Client
                # This overrides any previous logic to ensure reliability
                role = resolve_role_label(selected_client.get("papel"))
                is_rag_agent = (role == AgentRole.CLIENTE_SIMULADO_PADRAO) or ("Conversas Reais" in selected_client.get("nome", ""))
                
                forced_phrase = None
                if current_transcript_len == 0 and is_rag_agent and not scenario:
                     import random
                     rag_file = _resolve_rag_filename(selected_client)
                     if rag_file and rag_file.exists():
                        try:
                            lines = rag_file.read_text(encoding="utf-8").splitlines()
                            valid_phrases = [l.strip() for l in lines if l.strip() and not l.strip().startswith(("#", "*", "-"))]
                            if valid_phrases:
                                forced_phrase = random.choice(valid_phrases)
                                st.session_state.bot_test_auto_scenario = forced_phrase # Persist for consistency
                        except Exception:
                            pass

                if current_transcript_len == 0 and (scenario or forced_phrase):
                    reply_text = forced_phrase if forced_phrase else scenario
                    debug = {"source": "direct_scenario_rag"}
                    usage = {"input": 0, "output": 0, "total": 0}
                    error_msg = None
                else:
                    history_lines = []
                    recents = st.session_state.bot_test_auto_transcripts[-6:]
                    for msg in recents:
                         role = "Atendente" if msg['role'] == 'assistant' else "Cliente"
                         history_lines.append(f"{role}: {msg['content']}")
                    history_text = "\n".join(history_lines)
                    
                    prompt_msg = (
                        f"Histórico da conversa recente:\n{history_text}\n\n"
                        f"Última mensagem do atendente: '{last_bot_msg}'.\n"
                        "Responda como um cliente, mantendo a continuidade do assunto."
                    )

                    client_context = AgentContext(
                        mensagem=prompt_msg,
                        canal="playground_auto",
                        origem="playground_auto"
                    )
                    
                    
                    reply_text, debug, usage, error_msg = _run_client_agent_debug(
                        selected_client, 
                        client_context.mensagem, 
                        client_context,
                        log_path=st.session_state.get(f"debug_log_path_tests_auto_{bot['id']}")
                    )
                
                if reply_text:
                    reply_text = _clean_reply_text(reply_text)
                
                if error_msg:
                    st.error(f"Erro agente cliente: {error_msg}")
                    reply_text = f"[ERRO] {error_msg}"
                
                if not reply_text:
                    reply_text = "(Sem resposta do cliente)"
                
                st.session_state.bot_test_auto_transcripts.append({
                    "role": "user", 
                    "content": reply_text,
                    "usage": usage,
                    "debug": debug # Store debug
                })

                st.session_state.bot_test_auto_stats["total_tokens"] = _sum_usage(st.session_state.bot_test_auto_stats["total_tokens"], usage)
                st.session_state.bot_test_auto_next_turn = "bot"
                st.rerun()

            elif st.session_state.bot_test_auto_next_turn == "bot":
                try:
                    if not st.session_state.bot_test_auto_transcripts:
                         st.error("Erro de estado: Turno do bot mas sem mensagem anterior do cliente.")
                         st.session_state.bot_test_auto_running = False
                         st.stop()

                    last_client_msg = st.session_state.bot_test_auto_transcripts[-1]["content"]
                    
                    # Inject Bot Persona
                    orch_agent_copy = orchestrator_agent.copy()
                    if bot.get("persona"):
                        orch_agent_copy["bot_persona"] = bot.get("persona")

                    reply_text, debug, usage = _run_orchestrator_reply(
                        orch_agent_copy,
                        linked_agents,
                        agents_by_id,
                        last_client_msg,
                        log_path=st.session_state.get(f"debug_log_path_tests_auto_{bot['id']}")
                    )
                    
                    if reply_text:
                        reply_text = _clean_reply_text(reply_text)
                        
                    if not reply_text:
                        reply_text = DEFAULT_NO_RESPONSE

                except Exception as e:
                    st.error(f"Erro fatal executando Bot: {e}")
                    st.session_state.bot_test_auto_running = False
                    st.stop()
                    return

                st.session_state.bot_test_auto_transcripts.append({
                    "role": "assistant",
                    "content": reply_text,
                    "usage": usage,
                    "debug": debug, # Store debug
                    "agent_name": debug.get("responder", {}).get("nome"),
                })
                
                st.session_state.bot_test_auto_stats["total_tokens"] = _sum_usage(st.session_state.bot_test_auto_stats["total_tokens"], usage)
                st.session_state.bot_test_auto_last_bot_msg = reply_text
                
                st.session_state.bot_test_auto_next_turn = "client"
                time.sleep(1)
                st.rerun()


def _get_chat_state(bot_id: int) -> dict[str, Any]:
    if "bot_test_sessions" not in st.session_state:
        st.session_state.bot_test_sessions = {}
    sessions = st.session_state.bot_test_sessions
    if bot_id not in sessions:
        sessions[bot_id] = {
            "display": [], 
            "total_tokens": {"input": 0, "output": 0, "total": 0, "models": {}}
        }
    return sessions[bot_id]


def _run_orchestrator_reply(
    orchestrator_agent: dict[str, Any],
    linked_agents: list[dict[str, Any]],
    agents_by_id: dict[int, dict[str, Any]],
    user_prompt: str,
    log_path: Path | str | None = None,
) -> tuple[str, dict[str, Any], dict[str, Any] | None]:
    model_name = (orchestrator_agent.get("model") or "").strip()
    if not model_name:
        return "Modelo do agente orquestrador nao configurado.", {}, None

    context = AgentContext(
        mensagem=user_prompt,
        canal="playground",
        origem="playground",
    )
    debug_info = _init_debug_info(context, orchestrator_agent)
    agents_by_role = _map_agents_by_role(linked_agents, agents_by_id)
    
    # Execucao do roteador
    raw_reply, router_rag, usage_router = _run_agent_raw(orchestrator_agent, user_prompt, context, log_path=log_path)
    usage_total = _sum_usage(None, usage_router)
    
    debug_info["roteador"] = _merge_rag_debug(_agent_debug(orchestrator_agent), router_rag)
    if raw_reply is None:
        debug_info["responder"] = debug_info["roteador"]
        debug_info["rag"] = router_rag
        return "Erro ao gerar resposta com o agente orquestrador.", debug_info, usage_total

    parsed = _extract_json(raw_reply)
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
        return "Agente destino nao reconhecido.", debug_info, usage_total

    if destination_role == AgentRole.COORDENADOR:
        coordinator = agents_by_role.get(AgentRole.COORDENADOR)
        if not coordinator:
            debug_info["responder"] = debug_info["roteador"]
            debug_info["resposta"] = _summarize_payload(parsed)
            debug_info["rag"] = router_rag
            return "Agente coordenador nao encontrado.", debug_info, usage_total
            
        response_text, coordinator_payload, responder_agent, responder_payload, responder_rag, usage_coord = _run_coordinator_flow(
            coordinator, agents_by_role, user_prompt, context, log_path=log_path
        )
        usage_total = _sum_usage(usage_total, usage_coord)
        
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
        return "Agente destino nao encontrado.", debug_info, usage_total
        
    response_text, responder_payload, responder_rag, usage_dest = _run_agent_reply(
        destination_agent, user_prompt, context, log_path=log_path
    )
    usage_total = _sum_usage(usage_total, usage_dest)

    debug_info["responder"] = _merge_rag_debug(_agent_debug(destination_agent), responder_rag)
    debug_info["resposta"] = _summarize_payload(responder_payload)
    debug_info["rag"] = responder_rag
    
    if transition_msg:
         response_text = f"{transition_msg}\n\n{response_text}"
         if debug_info["responder"].get("nome"):
              debug_info["responder"]["nome"] = f"{orchestrator_agent['nome']} ▶ {debug_info['responder']['nome']}"

    return response_text, debug_info, usage_total


def _run_coordinator_flow(
    coordinator_agent: dict[str, Any],
    agents_by_role: dict[AgentRole, dict[str, Any]],
    user_prompt: str,
    context: AgentContext,
    log_path: Path | str | None = None,
) -> tuple[
    str,
    dict[str, Any] | None,
    dict[str, Any] | None,
    dict[str, Any] | None,
    dict[str, Any],
    dict[str, Any] | None,
]:
    raw_reply, coordinator_rag, usage_coord = _run_agent_raw(coordinator_agent, user_prompt, context, log_path=log_path)
    usage_total = _sum_usage(None, usage_coord)
    
    if raw_reply is None:
        return "Erro ao gerar resposta com o agente coordenador.", None, None, None, coordinator_rag, usage_total

    parsed = _extract_json(raw_reply)
    if parsed is None:
        return raw_reply or DEFAULT_NO_RESPONSE_DOT, None, coordinator_agent, None, coordinator_rag, usage_total

    if _needs_human(parsed, parsed.get("agente_destino")):
        return _handoff_message(parsed), parsed, coordinator_agent, parsed, coordinator_rag, usage_total

    action = _string_or_none(parsed.get("acao"))
    destination = parsed.get("agente_destino")
    if action == "redirecionar" and destination:
        destination_role = resolve_role_label(destination)
        if destination_role and destination_role in agents_by_role:
            response_text, responder_payload, responder_rag, usage_dest = _run_agent_reply(
                agents_by_role[destination_role], user_prompt, context, log_path=log_path
            )
            usage_total = _sum_usage(usage_total, usage_dest)
            return response_text, parsed, agents_by_role[destination_role], responder_payload, responder_rag, usage_total

    if _has_message(parsed):
        return _extract_message(parsed) or DEFAULT_NO_RESPONSE_DOT, parsed, coordinator_agent, parsed, coordinator_rag, usage_total

    return raw_reply or DEFAULT_NO_RESPONSE_DOT, parsed, coordinator_agent, parsed, coordinator_rag, usage_total


def _run_agent_reply(
    agent_record: dict[str, Any],
    user_prompt: str,
    context: AgentContext,
    log_path: Path | str | None = None,
) -> tuple[str, dict[str, Any] | None, dict[str, Any], dict[str, Any] | None]:
    raw_reply, rag_debug, usage = _run_agent_raw(agent_record, user_prompt, context, log_path=log_path)
    if raw_reply is None:
        return "Erro ao gerar resposta com o agente.", None, rag_debug, usage

    parsed = _extract_json(raw_reply)
    if parsed is None:
        return raw_reply or DEFAULT_NO_RESPONSE_DOT, None, rag_debug, usage

    if _needs_human(parsed, parsed.get("agente_destino")):
        return _handoff_message(parsed), parsed, rag_debug, usage

    if _has_message(parsed):
        return _extract_message(parsed) or DEFAULT_NO_RESPONSE_DOT, parsed, rag_debug, usage

    return raw_reply or DEFAULT_NO_RESPONSE_DOT, parsed, rag_debug, usage


def _run_agent_raw(
    agent_record: dict[str, Any],
    user_prompt: str,
    context: AgentContext,
    log_path: Path | str | None = None,
) -> tuple[str | None, dict[str, Any], dict[str, Any] | None]:
    model_name = (agent_record.get("model") or "").strip()
    
    # LOG: Start
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

    rag_context, rag_debug = _get_rag_context(agent_record, user_prompt)
    
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
    # Only use AgentReply for known roles that explicitly require it, excluding Client/Default
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
        result = run_async(agent.run(user_prompt))
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
    
    # LOG: Success
    if log_path:
         append_log(log_path, "agent_success", {"raw_reply": raw_result, "usage": usage_info})

    # LOG: Global History
    log_llm_interaction(
        agent_name=agent_record.get("nome"),
        model=model_name,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response=raw_result,
        usage=usage_info
    )

    return raw_result, rag_debug, usage_info


def _run_client_agent_debug(
    agent_record: dict[str, Any],
    user_prompt: str,
    context: AgentContext,
    log_path: Path | str | None = None,
) -> tuple[str | None, dict[str, Any], dict[str, Any] | None, str | None]:
    model_name = (agent_record.get("model") or "").strip()
    if not model_name:
        return None, {}, None, "Modelo nao configurado"

    try:
        api_key = get_settings().OPENAI_API_KEY
        if not api_key:
             return None, {}, None, "OPENAI_API_KEY nao encontrada"
    except Exception as e:
        return None, {}, None, f"Erro config: {e}"

    parts = []
    agent_prompt = (agent_record.get("system_prompt") or "").strip()
    if agent_prompt:
        parts.append(f"=== INSTRUÇÕES DO AGENTE ===\n{agent_prompt}")
    
    # Injected Logic: Force usage of phrases from local RAG file
    # Uses dynamic resolution based on agent's RAG
    role = resolve_role_label(agent_record.get("papel"))
    # Only enforce this for Client Agent to avoid polluting other agents unless desired
    if role == AgentRole.CLIENTE_SIMULADO_PADRAO:
        rag_file = _resolve_rag_filename(agent_record)
        
        if rag_file and rag_file.exists():
            try:
                content = rag_file.read_text(encoding="utf-8")
                parts.append(f"=== BASE DE FRASES E COMPORTAMENTO ===\n{content}\n\n[INSTRUÇÃO PRIORITÁRIA]: Para iniciar ou conduzir a conversa, SELECIONE UMA das frases/perguntas listadas acima. Não invente nada fora deste escopo se possível.")
            except Exception as e:
                print(f"Erro ao ler arquivo RAG local: {e}")

    if context.mensagem:
         parts.append(f"=== CONTEXTO ===\n{context.mensagem}")

    system_prompt = "\n\n".join(parts)

    agent = Agent(
        OpenAIModel(model_name, api_key=api_key),
        system_prompt=system_prompt,
        name=agent_record.get("nome"),
        result_type=str,
        defer_model_check=True,
    )
    
    try:
        result = run_async(agent.run(user_prompt))
        
        usage_info = None
        if hasattr(result, "usage"):
            usage = result.usage()
            usage_info = {
                "input": usage.request_tokens or 0,
                "output": usage.response_tokens or 0,
                "total": usage.total_tokens or 0,
            }
        
        raw_result = (result.data or "").strip()
            
        # LOG: Client Success
        if log_path:
            append_log(log_path, "client_agent_success", {"raw_reply": raw_result})

        # LOG: Global History
        log_llm_interaction(
            agent_name=agent_record.get("nome"),
            model=model_name,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=raw_result,
            usage=usage_info
        )

        return raw_result, {}, usage_info, None

    except Exception as exc:
        return None, {}, None, str(exc)


def _clean_reply_text(text: str) -> str:
    """Clips AgentReply prefix or JSON artifacts from response."""
    if not text:
        return ""
    
    clean = text.strip()
    
    clean = re.sub(r"^(?:<)?AgentReply(?:>)?[:\s]*", "", clean, flags=re.IGNORECASE).strip()
    clean = re.sub(r"^['\"]{3}\s*", "", clean) # Remove leading triple quotes
    clean = re.sub(r"['\"]{3}\s*$", "", clean) # Remove trailing triple quotes
    clean = re.sub(r"^(?:<)?AgentReply(?:>)?[:\s]*", "", clean, flags=re.IGNORECASE).strip() # Apply again after quotes
    clean = re.sub(r"</AgentReply>$", "", clean, flags=re.IGNORECASE).strip()
    if clean.startswith(":"):
        clean = clean[1:].strip()
        
    if (clean.startswith("(") and clean.endswith(")")) or \
       (clean.startswith("{") and clean.endswith("}")) or \
       (clean.startswith("[") and clean.endswith("]")):
        clean = clean[1:-1].strip()
    
    if (clean.startswith('"') and clean.endswith('"')) or \
       (clean.startswith("'") and clean.endswith("'")):
        clean = clean[1:-1]

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

    # 4.5 Aggressive Prefix Cleanup (Fix for 'text": "')
    # If JSON parsing failed, maybe it's a broken JSON string.
    # Ex: text": "Ola..."
    # Ex: "response": "Ola..."
    # We strip the "Key": " part.
    prefix_pattern = r'^\s*(?:["\']?)(?:response|resposta|mensagem|message|content|text|cliente|client|bot|atendente|assistant)(?:["\']?)\s*[:=]\s*["\']?'
    clean = re.sub(prefix_pattern, "", clean, flags=re.IGNORECASE).strip()

    loose_json_pattern = r'(?:["\']?)(?:response|resposta|mensagem|message|content|text|cliente|client|bot|atendente|assistant)(?:["\']?)\s*[:=]\s*["\'](.*?)["\']'
    m_loose = re.search(loose_json_pattern, clean, re.IGNORECASE | re.DOTALL)
    if m_loose:
        return m_loose.group(1)

    patterns = [
        r"(?:message|mensagem|response)\s*=\s*['\"](.*?)['\"](?:,|}|\)|$)",
        r"['\"](?:message|mensagem|response)['\"]\s*[:=]\s*['\"](.*?)['\"](?:,|}|\)|$)",
        r"AgentReply\s*\(\s*['\"](.*?)['\"]\s*\)",
        r"AgentReply\s*\{.*?['\"](?:message|mensagem|response)['\"]\s*:\s*['\"](.*?)['\"].*?\}"
    ]
    for pat in patterns:
        m = re.search(pat, clean, re.IGNORECASE | re.DOTALL)
        if m:
            return m.group(1)

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
                 return clean[first_quote+1:last_quote]

    if len(clean) < 5 and not any(c.isalnum() for c in clean):
        return ""

    return clean


def _sum_usage(u1: dict[str, int] | None, u2: dict[str, int] | None) -> dict[str, int]:
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


def _render_debug_info(info: dict[str, Any] | None, _advanced: bool = False) -> None:
    """Render debug info in an expander. Note: _advanced is kept for API compatibility."""
    if not info:
        return
    with st.expander("Detalhes da execucao"):
        st.json(info)

def _summarize_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    return {k: v for k, v in payload.items() if k not in ("mensagem", "message")}


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
    message = _string_or_none(payload.get("mensagem")) or _string_or_none(payload.get("message"))
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


def _query_chromadb(collection_name: str, query: str, top_k: int, log_path: Path | str | None = None) -> list[dict[str, Any]]:
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

        
    # LOG: RAG Query
    if log_path:
         append_log(log_path, "rag_query", {
             "collection": collection_name,
             "query": query,
             "results_count": len(results),
             "top_result": results[0] if results else None
         })

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


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None
