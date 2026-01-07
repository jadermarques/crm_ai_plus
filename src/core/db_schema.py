from __future__ import annotations

from sqlalchemy import text

from src.core.database import get_engine

_AUDIT_TRIGGER_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION set_data_hora_alteracao() RETURNS TRIGGER AS $$
BEGIN
  NEW.data_hora_alteracao = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

_AUDIT_COLUMNS = [
    "ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS data_hora_inclusao TIMESTAMPTZ NOT NULL DEFAULT now()",
    "ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS data_hora_alteracao TIMESTAMPTZ NOT NULL DEFAULT now()",
]


def _trigger_sql(table_name: str) -> str:
    trigger_name = f"trg_{table_name}_data_hora_alteracao"
    return f"""
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger t
    JOIN pg_class c ON t.tgrelid = c.oid
    WHERE t.tgname = '{trigger_name}'
  ) THEN
    CREATE TRIGGER {trigger_name}
    BEFORE UPDATE ON {table_name}
    FOR EACH ROW EXECUTE FUNCTION set_data_hora_alteracao();
  END IF;
END $$;
"""


async def ensure_audit_columns(table_name: str) -> None:
    """
    Garantir colunas padrão de auditoria e trigger de atualização para a tabela.
    """
    engine = get_engine()
    dialect = engine.sync_engine.dialect.name
    async with engine.begin() as conn:
        for statement in _AUDIT_COLUMNS:
            await conn.execute(text(statement.format(table_name=table_name)))
        if dialect == "postgresql":
            await conn.execute(text(_AUDIT_TRIGGER_FUNCTION_SQL))
            await conn.execute(text(_trigger_sql(table_name)))
