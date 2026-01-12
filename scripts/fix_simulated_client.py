import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio
from sqlalchemy import select, update
from src.core.agents import agents
from src.core.database import get_sessionmaker
from src.core.agent_architecture import AgentRole, AGENT_SYSTEM_PROMPTS

async def fix_agent():
    print("Fixing 'Cliente Simulado Padrão' agent configuration...")
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        # Find the agent
        query = select(agents).where(agents.c.papel == AgentRole.CLIENTE_SIMULADO_PADRAO.value)
        result = await session.execute(query)
        agent = result.mappings().first()

        if not agent:
            print("Agent not found! Creating it might be necessary, but usually it should strictly exist if seen in UI.")
            return

        print(f"Found agent: ID {agent['id']}, Name: {agent['nome']}")
        print(f"Current Model: {agent['model']}")
        print(f"Current Prompt Length: {len(agent['system_prompt'] or '')}")

        # Update
        new_prompt = AGENT_SYSTEM_PROMPTS[AgentRole.CLIENTE_SIMULADO_PADRAO]
        model = "gpt-4o"
        
        await session.execute(
            update(agents)
            .where(agents.c.id == agent["id"])
            .values(
                model=model,
                system_prompt=new_prompt,
                ativo=True
            )
        )
        await session.commit()
        print("Agent updated successfully!")

if __name__ == "__main__":
    try:
        asyncio.run(fix_agent())
    except Exception as e:
        print(f"Error: {e}")
