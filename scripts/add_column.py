import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio
from sqlalchemy import text
from src.core.database import get_engine

async def add_column():
    print("Adicionando coluna persona...")
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("ALTER TABLE bots ADD COLUMN IF NOT EXISTS persona TEXT"))
    print("Coluna adicionada (ou ja existia).")

if __name__ == "__main__":
    asyncio.run(add_column())
