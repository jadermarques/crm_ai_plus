
import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.agent_architecture import AGENT_SYSTEM_PROMPTS, resolve_role_label, AgentRole
from src.core.agents import list_agents, update_agent

async def main():
    print("Iniciando atualização de prompts dos agentes no banco de dados...")
    
    # 1. Fetch current agents
    agents = await list_agents(include_inactive=True)
    print(f"Encontrados {len(agents)} agentes.")
    
    updates_count = 0
    
    for agent in agents:
        agent_id = agent["id"]
        role_label = agent.get("papel")
        
        # Resolve role enum
        role = resolve_role_label(role_label)
        
        if not role:
            print(f"Skipping agent {agent['nome']} (ID {agent_id}): Papel desconhecido '{role_label}'")
            continue
            
        # Check if we have a standard prompt for this role
        if role not in AGENT_SYSTEM_PROMPTS:
            print(f"Skipping agent {agent['nome']} (ID {agent_id}): Sem prompt padrao para papel {role.value}")
            continue
            
        new_prompt = AGENT_SYSTEM_PROMPTS[role]
        current_prompt = (agent.get("system_prompt") or "").strip()
        
        # Normalize for comparison (ignore strict whitespace differences if minor, but simple strip is ok)
        if new_prompt.strip() == current_prompt:
            print(f"Agente {agent['nome']} (ID {agent_id}) ja esta atualizado.")
            continue
            
        print(f"Atualizando agente {agent['nome']} (ID {agent_id})...")
        
        # Prepare update
        # We must increment version
        current_version = agent.get("versao") or 1
        new_version = int(current_version) + 1
        
        try:
            await update_agent(
                agent_id=agent_id,
                nome=agent["nome"],
                descricao=agent.get("descricao"),
                system_prompt=new_prompt,
                model=agent["model"],
                versao=new_version,
                ativo=agent["ativo"],
                agente_orquestrador=agent["agente_orquestrador"],
                papel=role, # Pass Enum or string value
                rag_id=agent.get("rag_id")
            )
            print(f"--> Sucesso: Versao {new_version}")
            updates_count += 1
        except Exception as e:
            print(f"--> ERRO ao atualizar {agent['nome']}: {e}")
            
    print(f"\nConcluido. Total atualizados: {updates_count}")

if __name__ == "__main__":
    asyncio.run(main())
