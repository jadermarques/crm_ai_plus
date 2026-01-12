import sys
import asyncio
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.agents import list_agents

async def main():
    agents = await list_agents()
    for a in agents:
        if "simulado" in a.get("nome", "").lower() or "padrao" in a.get("nome", "").lower():
            print(f"--- Agent: {a.get('nome')} ---")
            print(f"ID: {a.get('id')}")
            print(f"Role: {a.get('papel')}")
            print(f"Model: {a.get('model')}")
            print(f"System Prompt Length: {len(a.get('system_prompt') or '')}")
            print(f"System Prompt Preview: {(a.get('system_prompt') or '')[:50]}...")
            print("-" * 30)

if __name__ == "__main__":
    asyncio.run(main())
