from __future__ import annotations

import argparse
import asyncio
import getpass
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.auth import ensure_users_table, create_user, update_password  # noqa: E402

_EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}(?:\.[^@\s]{2,})?$")


async def _create(username: str, password: str, full_name: str, email: str, role: str = "USER") -> None:
    await ensure_users_table()
    await create_user(
        username=username,
        password=password,
        full_name=full_name,
        email=email,
        role=role,
    )


async def _update(username: str, password: str) -> None:
    await ensure_users_table()
    await update_password(username=username, password=password)


def main() -> None:
    parser = argparse.ArgumentParser(description="Criar usuário do CRM AI Plus.")
    parser.add_argument("--username", "-u", required=False, help="Nome de usuário")
    parser.add_argument("--full-name", "-n", required=False, help="Nome completo")
    parser.add_argument("--email", "-e", required=False, help="E-mail do usuário")
    parser.add_argument(
        "--role",
        "-r",
        choices=["ADMIN", "USER"],
        default="USER",
        help="Tipo de usuário (ADMIN ou USER).",
    )
    parser.add_argument("--password", "-p", required=False, help="Senha (mínimo 6 caracteres)")
    parser.add_argument(
        "--update",
        action="store_true",
        help="Atualizar a senha de um usuário existente em vez de criar.",
    )
    args = parser.parse_args()

    username = (args.username or input("Usuário: ")).strip().lower()
    full_name = args.full_name or input("Nome completo: ").strip()
    email = args.email or input("E-mail: ").strip()
    role = (args.role or "USER").strip().upper()
    password = args.password or getpass.getpass("Senha (mínimo 6 caracteres): ")

    if len(username) < 3 or len(username) > 20:
        print("Erro: usuário deve ter entre 3 e 20 caracteres (minúsculas).", file=sys.stderr)
        raise SystemExit(1)
    if len(password) < 6:
        print("Erro: a senha deve ter pelo menos 6 caracteres.", file=sys.stderr)
        raise SystemExit(1)
    if not username or not full_name or not email:
        print("Erro: usuário, nome e e-mail são obrigatórios.", file=sys.stderr)
        raise SystemExit(1)
    if not _EMAIL_REGEX.match(email.strip().lower()):
        print("Erro: informe um e-mail válido.", file=sys.stderr)
        raise SystemExit(1)

    if args.update:
        asyncio.run(_update(username=username, password=password))
        print(f"Senha do usuário '{username}' atualizada com sucesso.")
    else:
        asyncio.run(
            _create(
                username=username,
                password=password,
                full_name=full_name,
                email=email,
                role=role,
            )
        )
        print(f"Usuário '{username}' criado com sucesso.")


if __name__ == "__main__":
    main()
