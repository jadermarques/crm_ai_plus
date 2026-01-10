"""
RAG Utilities - Consolidated RAG Functions

This module provides utilities for RAG (Retrieval Augmented Generation) operations
including file resolution, context retrieval, and ChromaDB integration.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Any

from src.core.agent_architecture import AgentRole, resolve_role_label
from src.core.constants import RAG_DATA_DIR


def resolve_rag_filename(
    agent: dict[str, Any],
    get_rag_by_id_fn: callable | None = None,
    run_async_fn: callable | None = None,
) -> Path | None:
    """
    Resolve the RAG file path based on the agent's RAG association.
    
    Convention: RAG-{normalized_name}.md based on the RAG name in the database.
    Fallback: For simulated client agents, tries the legacy pattern.
    
    Args:
        agent: Agent configuration dictionary
        get_rag_by_id_fn: Optional function to fetch RAG by ID from database
        run_async_fn: Optional function to run async code
        
    Returns:
        Path to the RAG file if found, None otherwise
    """
    rag_id = agent.get("rag_id")
    candidate_rag_file = None

    if rag_id and get_rag_by_id_fn and run_async_fn:
        try:
            rag = run_async_fn(get_rag_by_id_fn(rag_id))
            if rag:
                nome = rag.get("nome", "")
                if nome:
                    normalized = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii").lower()
                    slug = normalized.replace(" ", "-")

                    # Try RAG-{slug}.md
                    c1 = RAG_DATA_DIR / f"RAG-{slug}.md"
                    if c1.exists():
                        candidate_rag_file = c1

                    # Try exact name
                    if not candidate_rag_file:
                        c2 = RAG_DATA_DIR / nome
                        if c2.exists():
                            candidate_rag_file = c2

        except Exception as e:
            print(f"Erro resolvendo arquivo RAG (DB): {e}")

    # Fallback logic for simulated client
    if not candidate_rag_file:
        role = resolve_role_label(agent.get("papel"))
        if role == AgentRole.CLIENTE_SIMULADO_PADRAO:
            legacy = RAG_DATA_DIR / "RAG-cliente-conversas-reais.md"
            if legacy.exists():
                candidate_rag_file = legacy

    return candidate_rag_file


def resolve_rag_filename_simple(agent: dict[str, Any]) -> Path | None:
    """
    Simple RAG filename resolution without database lookup.
    
    Uses only the agent's role for fallback resolution.
    
    Args:
        agent: Agent configuration dictionary
        
    Returns:
        Path to the RAG file if found, None otherwise
    """
    role = resolve_role_label(agent.get("papel"))
    
    if role == AgentRole.CLIENTE_SIMULADO_PADRAO:
        legacy = RAG_DATA_DIR / "RAG-cliente-conversas-reais.md"
        if legacy.exists():
            return legacy
    
    # Try to resolve by agent name
    nome = agent.get("nome", "")
    if nome:
        normalized = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii").lower()
        slug = normalized.replace(" ", "-")
        
        candidate = RAG_DATA_DIR / f"RAG-{slug}.md"
        if candidate.exists():
            return candidate
    
    return None


def normalize_rag_name(name: str) -> str:
    """
    Normalize a name for RAG file naming.
    
    Converts to ASCII lowercase with hyphens.
    
    Args:
        name: The name to normalize
        
    Returns:
        Normalized name suitable for filename
    """
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    slug = normalized.lower().replace(" ", "-")
    return slug


def build_rag_file_path(name: str) -> Path:
    """
    Build the expected RAG file path for a given name.
    
    Args:
        name: The RAG name
        
    Returns:
        Path to the expected RAG file
    """
    slug = normalize_rag_name(name)
    return RAG_DATA_DIR / f"RAG-{slug}.md"


def list_rag_files() -> list[Path]:
    """
    List all RAG files in the data directory.
    
    Returns:
        List of paths to RAG markdown files
    """
    if not RAG_DATA_DIR.exists():
        return []
    
    return sorted(RAG_DATA_DIR.glob("*.md"))


def read_rag_content(file_path: Path, max_length: int | None = None) -> str:
    """
    Read content from a RAG file.
    
    Args:
        file_path: Path to the RAG file
        max_length: Optional maximum content length
        
    Returns:
        File content as string
    """
    if not file_path.exists():
        return ""
    
    try:
        content = file_path.read_text(encoding="utf-8")
        if max_length and len(content) > max_length:
            content = content[:max_length] + "..."
        return content
    except Exception as e:
        print(f"Erro ao ler arquivo RAG: {e}")
        return ""
