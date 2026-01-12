
import sys
import asyncio
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.frontend.views.bot_tests import _resolve_rag_filename
from src.core.agents import list_agents
from src.core.agent_architecture import AgentRole, resolve_role_label

async def fetch_client_agent():
    print("Listing agents...")
    try:
        agents = await list_agents()
        for agent in agents:
            role = resolve_role_label(agent.get("papel"))
            if role == AgentRole.CLIENTE_SIMULADO_PADRAO:
                return agent
    except Exception as e:
        print(f"Error listing agents: {e}")
    return None

def main():
    # Run async part to get agent
    agent = asyncio.run(fetch_client_agent())
    
    if not agent:
        print("Client Agent not found or error fetching.")
        return

    print(f"Found Client Agent: {agent.get('nome')} (ID: {agent.get('id')}, RAG ID: {agent.get('rag_id')})")
    print("Resolving RAG filename...")
    
    # Run sync part (which calls run_async internally)
    try:
        resolved_file = _resolve_rag_filename(agent)
        print(f"Resolved File: {resolved_file}")
        
        if resolved_file:
             print(f"Exists: {resolved_file.exists()}")
             if resolved_file.exists():
                 content = resolved_file.read_text(encoding="utf-8").splitlines()
                 print(f"Line count: {len(content)}")
                 print("First 5 lines:")
                 for l in content[:5]:
                     print(l)
    except Exception as e:
        print(f"Error during resolution: {e}")

if __name__ == "__main__":
    main()
