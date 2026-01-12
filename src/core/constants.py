"""
Centralized constants for CRM AI Plus.

This module provides a single source of truth for commonly used constants
across the application, reducing duplication and improving maintainability.
"""

from pathlib import Path

# -----------------------------------------------------------------------------
# Paths
# -----------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAG_DATA_DIR = PROJECT_ROOT / "data" / "rag_files"
DEBUG_LOGS_DIR = PROJECT_ROOT / "logs" / "debug_runs"

# -----------------------------------------------------------------------------
# Default Messages
# -----------------------------------------------------------------------------
DEFAULT_NO_RESPONSE = "(Sem resposta)"
DEFAULT_NO_RESPONSE_DOT = "Sem resposta."
DEFAULT_AGENT_ERROR = "Erro ao gerar resposta com o agente."
DEFAULT_DESTINATION_NOT_FOUND = "Agente destino nao encontrado."
DEFAULT_COORDINATOR_NOT_FOUND = "Agente coordenador nao encontrado."
DEFAULT_DESTINATION_UNKNOWN = "Agente destino nao reconhecido."
DEFAULT_MODEL_NOT_CONFIGURED = "Modelo do agente nao configurado."
DEFAULT_HANDOFF_MESSAGE = "Um atendente humano entrará em contato em breve."

# -----------------------------------------------------------------------------
# Simulation Limits
# -----------------------------------------------------------------------------
MAX_SAFETY_TURNS = 25
DEFAULT_CHAT_CONTAINER_HEIGHT = 400

# -----------------------------------------------------------------------------
# Debug & Logging
# -----------------------------------------------------------------------------
DEBUG_LOG_PREFIX = "debug_"
DEBUG_LOG_EXTENSION = ".jsonl"

# -----------------------------------------------------------------------------
# Audio (Bot Simulator)
# -----------------------------------------------------------------------------
VOICE_BOT = "pt-BR-FranciscaNeural"
VOICE_CLIENT = "pt-BR-AntonioNeural"

# -----------------------------------------------------------------------------
# RAG Configuration
# -----------------------------------------------------------------------------
DEFAULT_RAG_TOP_K = 5
RAG_CONTEXT_MAX_LENGTH = 2000

# -----------------------------------------------------------------------------
# Agent Roles - String Values (for comparison with DB values)
# -----------------------------------------------------------------------------
ROLE_TRIAGEM = "triagem"
ROLE_COMERCIAL = "comercial"
ROLE_GUIA_UNIDADES = "guia_unidades"
ROLE_COTADOR = "cotador"
ROLE_CONSULTOR_TECNICO = "consultor_tecnico"
ROLE_RESUMO = "resumo"
ROLE_COORDENADOR = "coordenador"
ROLE_CLIENTE_SIMULADO = "cliente_simulado_padrao"
