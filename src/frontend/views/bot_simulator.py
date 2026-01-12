from __future__ import annotations

import csv
import io
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
import tempfile
import asyncio
import os
import re
import ast
import json

import streamlit as st
from gtts import gTTS
import edge_tts

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.agent_architecture import AgentContext, resolve_role_label, AgentRole
from src.core.agents import list_agents
from src.core.bots import ensure_tables, list_bot_agents, list_bots
from src.frontend.shared import page_header, render_db_status, run_async, render_debug_panel
from src.frontend.views.bot_tests import _run_orchestrator_reply
from src.core.config import get_settings
from src.core.debug_logger import create_log_session, append_log, log_llm_interaction

# NEW: Import shared modules
from src.core.constants import (
    DEFAULT_NO_RESPONSE,
    MAX_SAFETY_TURNS,
    VOICE_BOT as CONST_VOICE_BOT,
    VOICE_CLIENT as CONST_VOICE_CLIENT,
)
from src.core.orchestration import (
    clean_reply_text as _shared_clean_reply_text,
    sum_usage as _shared_sum_usage,
)
from src.core.rag_utils import resolve_rag_filename_simple

# Audio voice constants (kept for backward compatibility, now from constants)
VOICE_BOT = CONST_VOICE_BOT
VOICE_CLIENT = CONST_VOICE_CLIENT

import subprocess


async def _gen_audio_async(text: str, voice: str) -> str:
    # Adding rate=+50% for 1.5x speed playback
    communicate = edge_tts.Communicate(text, voice, rate="+50%")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
        await communicate.save(fp.name)
        return fp.name

def _process_audio_ffmpeg(input_path: str, is_male: bool = False, speed_factor: float = 2.0) -> str:
    """Uses ffmpeg to apply speed and pitch effects."""
    try:
        # Create temp output path
        fd, output_path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        
        # Build filter chain
        # Base speed filter
        # Note: atempo is limited to [0.5, 2.0]. If we need more, we chain.
        # But 2.0 is our target for now.
        
        if is_male:
            # Male synthesis for gTTS (Fake it by lowering pitch/rate and compensating speed)
            # 1. asetrate=24000*0.8 makes it 0.8x speed and lower pitch.
            # 2. To get final 2.0x speed relative to original, we need to speed up by 2.0 / 0.8 = 2.5x
            # 3. 2.5x requires chaining atempo=2.0, atempo=1.25
            
            # Assuming gTTS output is approx 24k or can simply be treated as such for the shift effect
            # We use 22050 as base reference to be safe or just relative factor.
            # actually asetrate sets the playback rate. If original is 24k, asetrate=19200 drops pitch.
            # Let's rely on a simpler 'rubberband' if available? No, not standard.
            # Let's use generic atempo for speed, and assume standard voice.
            # To JUST lower pitch without massive calc, let's use:
            # asetrate=24000*0.75, aresample=24000, atempo=2.0/(0.75) -> atempo=2.66
            
            # Calculating atempo parts for 2.66: 2.0 * 1.333
            
            # Using assumed sample rate of 24000 for gTTS 'pt'
            filter_complex = "asetrate=24000*0.75,aresample=24000,atempo=2.0,atempo=1.33"
        else:
            # Just Speed 2.0
            filter_complex = "atempo=2.0"

        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-filter:a", filter_complex,
            "-vn", # no video
            output_path
        ]
        
        # Run ffmpeg
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        return output_path
    
    except Exception as e:
        print(f"FFmpeg error: {e}")
        # Fallback to original if fails
        return input_path

def _gen_audio_gtts(text: str, is_male: bool) -> str:
    # Use Google TTS
    # 1. Generate Raw
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
        raw_path = fp.name
    
    tts = gTTS(text=text, lang='pt', slow=False)
    tts.save(raw_path)
    
    # 2. Process with ffmpeg for Speed (2.0x) and Pitch (Masking)
    final_path = _process_audio_ffmpeg(raw_path, is_male=is_male, speed_factor=2.0)
    
    # Clean up raw if different
    if final_path != raw_path:
        try:
            os.remove(raw_path)
        except OSError:
            pass
            
    return final_path

def _generate_audio(text: str, engine: str = "edge", voice: str = VOICE_BOT) -> str | None:
    try:
        if engine == "gtts":
            # Determine if we want "Masculine" feel based on voice arg mapping
            # VOICE_CLIENT (Antonio) -> Male
            # VOICE_BOT (Francisca) -> Female
            is_male = (voice == VOICE_CLIENT)
            return _gen_audio_gtts(text, is_male=is_male)
        else:
            return run_async(_gen_audio_async(text, voice))
    except Exception as e:
        print(f"Erro audio: {e}")
        return None

def _estimate_audio_duration(text: str) -> float:
    # Heuristic: 1.8 words per second + 2.0s buffer
    words = len(text.split())
    duration = (words / 1.8) + 2.0
    return max(3.5, duration)


# Local implementation to catch errors
def _run_agent_raw_debug(
    agent_record: dict[str, Any],
    user_prompt: str,
    context: AgentContext,
    log_path: Path | str | None = None,
) -> tuple[str | None, dict[str, Any], dict[str, Any] | None, str | None]:
    model_name = (agent_record.get("model") or "").strip()
    
    # LOG: Start
    if log_path:
        append_log(log_path, "agent_start", {
            "agent_name": agent_record.get("nome"),
            "user_prompt": user_prompt,
            "context_msg": context.mensagem
        })

    if not model_name:
        return None, {}, None, "Modelo nao configurado"

    try:
        api_key = get_settings().OPENAI_API_KEY
        if not api_key:
             return None, {}, None, "OPENAI_API_KEY nao encontrada"
    except Exception as e:
        return None, {}, None, f"Erro config: {e}"

    # Simple Prompt Construction
    parts = []
    agent_prompt = (agent_record.get("system_prompt") or "").strip()
    if agent_prompt:
        parts.append(f"=== INSTRUÇÕES DO AGENTE ===\n{agent_prompt}")
    
    # Context injection
    if context.mensagem:
         parts.append(f"=== CONTEXTO ===\n{context.mensagem}")

    system_prompt = "\n\n".join(parts)

    # LOG: System Prompt
    if log_path:
        append_log(log_path, "system_prompt_built", {"system_prompt": system_prompt})

    agent = Agent(
        OpenAIModel(model_name, api_key=api_key),
        system_prompt=system_prompt,
        name=agent_record.get("nome"),
        result_type=str,
        defer_model_check=True,
    )
    
    try:
        # Synch run in async context wrapper
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

        return raw_result, {}, usage_info, None

    except Exception as exc:
        # LOG: Error
        if log_path:
             append_log(log_path, "agent_error", {"error": str(exc)})
        return None, {}, None, str(exc)

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

def _clean_reply_text(text: str) -> str:
    """Clips AgentReply prefix or JSON artifacts from response."""
    if not text:
        return ""
    
    clean = text.strip()
    
    # 1. Strip AgentReply prefix using Regex to catch colon, spaces, and XML tags
    clean = re.sub(r"^(?:<)?AgentReply(?:>)?[:\s]*", "", clean, flags=re.IGNORECASE).strip()
    clean = re.sub(r"^['\"]{3}\s*", "", clean) # Remove leading triple quotes
    clean = re.sub(r"['\"]{3}\s*$", "", clean) # Remove trailing triple quotes
    clean = re.sub(r"^(?:<)?AgentReply(?:>)?[:\s]*", "", clean, flags=re.IGNORECASE).strip() # Apply again after quotes
    
    # Remove closing tag if present
    clean = re.sub(r"</AgentReply>$", "", clean, flags=re.IGNORECASE).strip()
    
    # Extra check if a colon remained
    if clean.startswith(":"):
        clean = clean[1:].strip()
        
    # 2. Strip wrapping (), {}, [] if they balance at ends
    if (clean.startswith("(") and clean.endswith(")")) or \
       (clean.startswith("{") and clean.endswith("}")) or \
       (clean.startswith("[") and clean.endswith("]")):
        clean = clean[1:-1].strip()
    
    # 3. Strip surrounding quotes if present
    if (clean.startswith('"') and clean.endswith('"')) or \
       (clean.startswith("'") and clean.endswith("'")):
        clean = clean[1:-1]

    # 4. Try parsing as Dict using ast.literal_eval
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
            # Fallback: First string value
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

    # 5. Regex Fallback
    # Matches: "key": "value" or key": "value" or key: "value"
    # Added keys: cliente, client, bot, atendente, assistant
    # Matches: "key": "value" or key": "value" or key: "value"
    # Added keys: cliente, client, bot, atendente, assistant
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

    # 6. Last Resort
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

    # 7. Garbage Filter
    # If the remaining text is very short and contains no alphanumeric characters, it's likely garbage.
    if len(clean) < 5 and not any(c.isalnum() for c in clean):
        return ""

    return clean

def _resolve_rag_filename(agent: dict[str, Any]) -> Path | None:
    """
    Resolve o nome do arquivo RAG local baseado no agente.
    Duplicado de bot_tests.py para isolamento.
    """
    import unicodedata
    
    # 1. Tenta pelo ID do RAG se existir
    rag_id = agent.get("rag_id")
    if rag_id:
        # Tenta resolver ID via DB se possível, mas aqui vamos focar no arquivo local
        # Se tivessemos acesso ao `get_rag_by_id`, usariamos.
        pass

    # 2. Convenção por Nome: RAG-{slug_do_nome}.md
    nome = agent.get("nome", "")
    if nome:
        normalized_name = unicodedata.normalize('NFKD', nome).encode('ASCII', 'ignore').decode('ASCII')
        slug = re.sub(r'[^a-zA-Z0-9]+', '-', normalized_name.lower()).strip('-')
        candidate = PROJECT_ROOT / "data/rag_files" / f"RAG-{slug}.md"
        if candidate.exists():
            return candidate

    # 3. Fallback Específico para Cliente Simulado Padrão
    role = resolve_role_label(agent.get("papel"))
    if role == AgentRole.CLIENTE_SIMULADO_PADRAO or "Conversas Reais" in nome:
         fallback = PROJECT_ROOT / "data/rag_files" / "RAG-cliente-conversas-reais.md"
         if fallback.exists():
             return fallback
             
    return None


def render() -> None:
    page_header("Simulador de Bot", "Teste autônomo entre Bot e Agente Cliente.")
    render_db_status()
    run_async(ensure_tables())

    # --- Setup & Selection ---
    col_setup = st.columns([1, 1, 1])
    
    # Bot Selector
    bots_data = run_async(list_bots())
    bot_options = {f"{b['nome']} (v{b['versao']})": b for b in bots_data if b['ativo']}
    selected_bot_label = col_setup[0].selectbox("Bot para Teste", list(bot_options.keys()) if bot_options else [])
    selected_bot = bot_options[selected_bot_label] if selected_bot_label else None

    # Client Agent Selector
    agents_data = run_async(list_agents())
    valid_clients = []
    for a in agents_data:
         role_val = a.get("papel")
         if role_val == AgentRole.CLIENTE_SIMULADO_PADRAO or (a.get("nome") and "simulado" in a["nome"].lower()):
             valid_clients.append(a)
             
    client_options = {f"{a['nome']} ({a['papel']})": a for a in valid_clients if a['ativo']}
    default_client_idx = 0
    for idx, label in enumerate(client_options.keys()):
        if "Cliente Simulado" in label:
            default_client_idx = idx
            break
            
    selected_client_label = col_setup[1].selectbox("Agente Cliente", list(client_options.keys()) if client_options else [], index=default_client_idx)
    selected_client = client_options[selected_client_label] if selected_client_label else None

    # Settings
    # min_interactions removed as per user request
    auto_play_audio = col_setup[2].checkbox("Áudio Automático", value=False, help="Gera e reproduz áudio automaticamente.")
    
    # Audio Engine Selector
    audio_engine_label = col_setup[2].selectbox("Motor de Áudio", ["Edge TTS (Melhor)", "Google TTS (Rápido)"], index=0)
    audio_engine_key = "gtts" if "Google" in audio_engine_label else "edge"

    # LOG PATH: Retrieved from shared debug panel (at bottom)
    log_path = st.session_state.get("debug_log_path_simulator")

    # Optional Scenario
    initial_scenario = st.text_input("Contexto Inicial / Cenário (Opcional)", placeholder="Ex: Pergunte sobre preço de pneu para Corolla 2020.")

    # --- Self-Correction / Setup Help ---
    if selected_client:
        model_check = (selected_client.get("model") or "").lower()
        prompt_check = selected_client.get("system_prompt")
        
        if not model_check or not prompt_check:
            st.warning(f"O agente '{selected_client['nome']}' parece desconfigurado (sem modelo ou prompt).")
            if st.button("Reparar Configuração do Agente", type="primary"):
                from src.core.agents import update_agent, AGENT_SYSTEM_PROMPTS
                
                new_prompt = AGENT_SYSTEM_PROMPTS.get(AgentRole.CLIENTE_SIMULADO_PADRAO)
                if selected_client.get("papel") == AgentRole.CLIENTE_SIMULADO_PADRAO:
                     new_prompt = AGENT_SYSTEM_PROMPTS[AgentRole.CLIENTE_SIMULADO_PADRAO]

                if not new_prompt:
                     new_prompt = "Você é um cliente simulado. Aja naturalmente."

                try:
                    run_async(update_agent(
                        selected_client["id"],
                        nome=selected_client["nome"],
                        descricao=selected_client.get("descricao"),
                        system_prompt=new_prompt,
                        model="gpt-4o",
                        versao=(selected_client.get("versao") or 1) + 1,
                        ativo=True,
                        agente_orquestrador=selected_client.get("agente_orquestrador", False),
                        papel=selected_client.get("papel") or AgentRole.CLIENTE_SIMULADO_PADRAO,
                        rag_id=selected_client.get("rag_id")
                    ))
                    st.success("Agente reparado! Recarregue a página.")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao reparar: {e}")

    # State Init
    if "simulator_running" not in st.session_state:
        st.session_state.simulator_running = False
    if "simulator_transcripts" not in st.session_state:
        st.session_state.simulator_transcripts = []
    if "simulator_stats" not in st.session_state:
        st.session_state.simulator_stats = {"start_time": None, "end_time": None, "total_tokens": {"input": 0, "output": 0, "total": 0}}
    if "simulator_audio_map" not in st.session_state:
        st.session_state.simulator_audio_map = {}
    if "simulator_scenario" not in st.session_state:
        st.session_state.simulator_scenario = ""

    # --- Debug Panel (Standardized) ---
    # Moved to bottom

    # Controls
    controls = st.columns([1, 1, 1])
    start_btn = controls[0].button("Iniciar Simulação", type="primary", disabled=st.session_state.simulator_running, use_container_width=True)
    stop_btn = controls[1].button("Parar", type="secondary", disabled=not st.session_state.simulator_running, use_container_width=True)
    clear_btn = controls[2].button("Limpar Conversa", type="secondary", disabled=st.session_state.simulator_running, use_container_width=True)
    
    if clear_btn:
        st.session_state.simulator_transcripts = []
        st.session_state.simulator_stats = {"start_time": None, "end_time": None, "total_tokens": {"input": 0, "output": 0, "total": 0}}
        st.session_state.simulator_audio_map = {}
        st.session_state.simulator_scenario = ""
        st.rerun()
    
    if start_btn and selected_bot and selected_client:
        st.session_state.simulator_running = True
        st.session_state.simulator_transcripts = []
        st.session_state.simulator_stats = {
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "total_tokens": {"input": 0, "output": 0, "total": 0, "models": {}}
        }
        st.session_state.simulator_next_turn = "client"
        st.session_state.simulator_last_bot_msg = "Olá, sou o assistente virtual."
        st.session_state.simulator_scenario = initial_scenario
        st.rerun()

    if stop_btn:
        st.session_state.simulator_running = False
        st.session_state.simulator_stats["end_time"] = datetime.now().isoformat()
        st.session_state.simulator_audio_map = {}
        st.rerun()

    # --- Live Feed ---
    st.divider()
    
    stats = st.session_state.simulator_stats["total_tokens"]
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
    for idx, msg in enumerate(st.session_state.simulator_transcripts):
        if msg['role'] == 'assistant':
             agent_suffix = f" - {msg.get('agent_name')}" if msg.get("agent_name") else ""
             role_label = f"🤖 Bot ({selected_bot['nome'] if selected_bot else 'Bot'}{agent_suffix})"
             avatar = "🤖"
        else:
             role_label = f"👤 Client"
             if selected_client:
                 role_label = f"👤 Cliente ({selected_client['nome']}) [{selected_client.get('papel', '')}]"
             avatar = "👤"

        with chat_container.chat_message(msg['role'], avatar=avatar):
            st.caption(role_label)
            st.write(msg['content'])
            
            # Audio Controls
            msg_hash = f"{idx}_{hash(msg['content'])}"
            if msg_hash in st.session_state.simulator_audio_map:
                do_autoplay = auto_play_audio and (idx == len(st.session_state.simulator_transcripts) - 1)
                st.audio(st.session_state.simulator_audio_map[msg_hash], format="audio/mp3", autoplay=do_autoplay)
            else:
                if st.button("🔊 Ouvir", key=f"btn_audio_{idx}"):
                    with st.spinner("Gerando áudio..."):
                         v_voice = VOICE_BOT if msg['role'] == 'assistant' else VOICE_CLIENT
                         audio_path = _generate_audio(msg['content'], engine=audio_engine_key, voice=v_voice)
                         if audio_path:
                             st.session_state.simulator_audio_map[msg_hash] = audio_path
                             st.rerun()
            
            if msg.get('usage'):
                u = msg['usage']
                st.caption(f"Tokens: In {u['input']} / Out {u['output']} / Total {u['total']}")

    # --- Execution Loop ---
    if st.session_state.simulator_running:
        interaction_count = len([m for m in st.session_state.simulator_transcripts if m['role'] == 'assistant'])
        
        # Limitador de segurança para evitar loops infinitos
        MAX_SAFETY_TURNS = 25
        if interaction_count >= MAX_SAFETY_TURNS:
            st.warning(f"Simulação pausada por segurança ({MAX_SAFETY_TURNS} interações).")
            st.session_state.simulator_running = False
            st.session_state.simulator_stats["end_time"] = datetime.now().isoformat()
            st.rerun()
            return

        # Check termination phrase in last message
        if st.session_state.simulator_transcripts:
            last_msg = st.session_state.simulator_transcripts[-1]
            if last_msg["role"] == "user": # Client termination
                 content = last_msg["content"].upper()
                 # Check for the standardized closing phrase or variations
                 if "TCHAU" in content and "OBRIGADO" in content:
                     st.success("Simulação concluída! O cliente encerrou a conversa.")
                     st.session_state.simulator_running = False
                     st.session_state.simulator_stats["end_time"] = datetime.now().isoformat()
                     st.balloons()
                     st.rerun()
                     return

        with st.spinner("Simulando..."):
            linked_agents = run_async(list_bot_agents(selected_bot["id"])) if selected_bot else []
            agents_by_id = {a["id"]: a for a in run_async(list_agents())}
            orchestrator_link = next((l for l in linked_agents if l.get("role") == "orquestrador"), None)
            orchestrator_agent = agents_by_id.get(orchestrator_link["agent_id"]) if orchestrator_link else None

            if not orchestrator_agent:
                st.error("Bot sem orquestrador! Parando.")
                st.session_state.simulator_running = False
                st.stop()
            
            # --- Turn Logic ---
            if st.session_state.simulator_next_turn == "client":
                last_bot_msg = st.session_state.simulator_last_bot_msg
                current_transcript_len = len(st.session_state.simulator_transcripts)
                scenario = st.session_state.get("simulator_scenario")
                
                # Robust RAG Injection Strategy (Ported from bot_tests.py)
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
                                st.session_state.simulator_scenario = forced_phrase # Persist for awareness
                        except Exception:
                            pass

                if current_transcript_len == 0 and (scenario or forced_phrase):
                    final_scenario = forced_phrase if forced_phrase else scenario
                    prompt_msg = f"O usuário definiu este cenário de teste: '{final_scenario}'. Inicie a conversa com o atendente baseado nisso."
                    # Direct Override if it was a forced phrase (simulate "user" input directly without LLM)
                    if forced_phrase:
                        # Skip LLM, inject directly
                        st.session_state.simulator_transcripts.append({
                            "role": "user", 
                            "content": forced_phrase,
                            "usage": {"input": 0, "output": 0, "total": 0},
                            "timestamp": datetime.now().isoformat()
                        })
                        st.session_state.simulator_next_turn = "bot"
                        st.rerun()
                        return

                else:
                    history_lines = []
                    recents = st.session_state.simulator_transcripts[-6:]
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
                    canal="simulador",
                    origem="simulador"
                )
                
                reply_text, debug, usage, error_msg = _run_agent_raw_debug(
                    selected_client, 
                    client_context.mensagem, 
                    client_context,
                    log_path=log_path
                )
                
                if reply_text:
                    reply_text = _clean_reply_text(reply_text)
                
                if error_msg:
                    st.error(f"Erro agente cliente: {error_msg}")
                    reply_text = f"[ERRO] {error_msg}"
                
                if not reply_text:
                    reply_text = "(Sem resposta do cliente)"
                
                st.session_state.simulator_transcripts.append({
                    "role": "user", 
                    "content": reply_text,
                    "usage": usage,
                    "timestamp": datetime.now().isoformat()
                })

                if auto_play_audio:
                    msg_hash = f"{len(st.session_state.simulator_transcripts)-1}_{hash(reply_text)}"
                    audio_path = _generate_audio(reply_text, engine=audio_engine_key, voice=VOICE_CLIENT)
                    if audio_path:
                         st.session_state.simulator_audio_map[msg_hash] = audio_path
                         duration = _estimate_audio_duration(reply_text)
                         with st.spinner(f"Reproduzindo... (~{duration:.1f}s)"):
                             time.sleep(duration + 0.5)

                st.session_state.simulator_stats["total_tokens"] = _sum_usage(st.session_state.simulator_stats["total_tokens"], usage)
                st.session_state.simulator_next_turn = "bot"
                st.rerun()

            elif st.session_state.simulator_next_turn == "bot":
                try:
                    if not st.session_state.simulator_transcripts:
                         st.error("Erro de estado: Turno do bot mas sem mensagem anterior do cliente.")
                         st.session_state.simulator_running = False
                         st.stop()

                    last_client_msg = st.session_state.simulator_transcripts[-1]["content"]
                    
                    # Inject Bot Persona
                    orch_agent_copy = orchestrator_agent.copy()
                    if selected_bot.get("persona"):
                        orch_agent_copy["bot_persona"] = selected_bot.get("persona")

                    reply_text, debug, usage = _run_orchestrator_reply(
                        orch_agent_copy,
                        linked_agents,
                        agents_by_id,
                        last_client_msg
                    )
                    
                    if reply_text:
                        reply_text = _clean_reply_text(reply_text)
                        
                    if not reply_text:
                        reply_text = "(Sem resposta)" # Fallback for empty bot response

                except Exception as e:
                    st.error(f"Erro fatal executando Bot: {e}")
                    import traceback
                    st.code(traceback.format_exc())
                    st.session_state.simulator_running = False
                    st.stop()
                    return

                st.session_state.simulator_transcripts.append({
                    "role": "assistant",
                    "content": reply_text,
                    "usage": usage,
                    "timestamp": datetime.now().isoformat(),
                    "agent_name": debug.get("responder", {}).get("nome"),
                })
                
                if auto_play_audio:
                    msg_hash = f"{len(st.session_state.simulator_transcripts)-1}_{hash(reply_text)}"
                    audio_path = _generate_audio(reply_text, engine=audio_engine_key, voice=VOICE_BOT)
                    if audio_path:
                         st.session_state.simulator_audio_map[msg_hash] = audio_path
                         duration = _estimate_audio_duration(reply_text)
                         with st.spinner(f"Reproduzindo... (~{duration:.1f}s)"):
                             time.sleep(duration + 0.5)
                
                st.session_state.simulator_stats["total_tokens"] = _sum_usage(st.session_state.simulator_stats["total_tokens"], usage)
                st.session_state.simulator_last_bot_msg = reply_text
                
                st.session_state.simulator_next_turn = "client"
                time.sleep(1) # Visual breather
                st.rerun()

    # --- Export ---
    if st.session_state.simulator_transcripts:
        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer)
        writer.writerow(["Timestamp", "Role", "Agent", "Content", "Tokens Total"])
        
        for msg in st.session_state.simulator_transcripts:
            agent_name = selected_bot['nome'] if msg['role'] == 'assistant' else selected_client['nome']
            usage_data = msg.get("usage") or {}
            writer.writerow([
                msg.get("timestamp"),
                msg["role"],
                agent_name,
                msg["content"],
                usage_data.get("total", 0)
            ])
            
        st.download_button(
            label="Exportar CSV",
            data=csv_buffer.getvalue(),
            file_name=f"simulacao_bot_{int(time.time())}.csv",
            mime="text/csv",
            use_container_width=True
        )

    # --- Debug Panel (Standardized) ---
    render_debug_panel("simulator")
