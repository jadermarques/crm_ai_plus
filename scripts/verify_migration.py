import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio
from sqlalchemy import select
from src.core.database import get_sessionmaker
from src.core.bots import bots
from src.core.agents import agents as agents_table

async def verify():
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        # Check Bot Persona
        stmt = select(bots.c.nome, bots.c.persona).where(bots.c.nome.ilike("%Galo%"))
        result = await session.execute(stmt)
        bot = result.first()
        print(f"BOT: {bot.nome}")
        print("-" * 20)
        print(bot.persona)
        print("=" * 40)
        
        # Check Agents
        stmt_agents = select(
            agents_table.c.nome, 
            agents_table.c.system_prompt,
            agents_table.c.agente_orquestrador
        ).where(agents_table.c.ativo == True)
        result_agents = await session.execute(stmt_agents)
        for agent in result_agents:
            print(f"AGENT: {agent.nome} | Orquestrador: {agent.agente_orquestrador}")
            print("-" * 20)
            print((agent.system_prompt or "")[:100] + "...") # Preview
            print("=" * 40)

if __name__ == "__main__":
    asyncio.run(verify())
