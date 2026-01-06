from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.auth import ensure_users_table, create_user, update_password  # noqa: E402


async def _create(username: str, password: str) -> None:
    await ensure_users_table()
    await create_user(username=username, password=password)


async def _update(username: str, password: str) -> None:
    await ensure_users_table()
    await update_password(username=username, password=password)


def main() -> None:
    parser = argparse.ArgumentParser(description="Criar usuário do CRM AI Plus.")
    parser.add_argument("--username", "-u", required=False, help="Nome de usuário")
    parser.add_argument("--password", "-p", required=False, help="Senha (mínimo 6 caracteres)")
    parser.add_argument(
        "--update",
        action="store_true",
        help="Atualizar a senha de um usuário existente em vez de criar.",
    )
    args = parser.parse_args()

    username = args.username or input("Usuário: ").strip()
    password = args.password or getpass.getpass("Senha (mínimo 6 caracteres): ")

    if len(password) < 6:
        print("Erro: a senha deve ter pelo menos 6 caracteres.", file=sys.stderr)
        raise SystemExit(1)

    if args.update:
        asyncio.run(_update(username=username, password=password))
        print(f"Senha do usuário '{username}' atualizada com sucesso.")
    else:
        asyncio.run(_create(username=username, password=password))
        print(f"Usuário '{username}' criado com sucesso.")


if __name__ == "__main__":
    main()
