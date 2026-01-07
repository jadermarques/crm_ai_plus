from __future__ import annotations

from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    func,
    select,
    text,
    and_,
    join,
)
from sqlalchemy.exc import SQLAlchemyError

from src.core.auth import ensure_users_table, get_user_by_id
from src.core.database import get_engine, get_sessionmaker
from src.core.db_schema import ensure_audit_columns

metadata = MetaData()
_DEFAULT_MODULES: list[dict[str, str]] = [
    {"name": "Principal", "description": "Área principal do workspace."},
    {"name": "Bot Studio", "description": "Gestão e configuração dos bots."},
    {"name": "Agentes de IA", "description": "Agentes inteligentes e suas configurações."},
    {"name": "IA e RAG", "description": "Recursos de IA e recuperação aumentada."},
    {"name": "Dashboard / Relatórios", "description": "Painéis e relatórios."},
    {"name": "Gestão", "description": "Administração geral do sistema."},
    {"name": "Testes", "description": "Execução e monitoramento de testes."},
    {"name": "Conexões Externas", "description": "Integrações externas e conexões."},
]
_DEFAULT_APPLICATIONS: list[dict[str, str | bool]] = [
    {"module": "Principal", "name": "Visão Geral", "description": "Resumo geral do workspace.", "is_active": True},
    {"module": "Bot Studio", "name": "Bots", "description": "Gestão de bots.", "is_active": True},
    {"module": "Bot Studio", "name": "Prompts", "description": "Catálogo de prompts dos bots.", "is_active": True},
    {"module": "Bot Studio", "name": "Configurações", "description": "Configurações do Bot Studio.", "is_active": True},
    {"module": "Bot Studio", "name": "Monitoramento", "description": "Monitoramento de bots.", "is_active": True},
    {"module": "Bot Studio", "name": "Testes", "description": "Testes de bots.", "is_active": True},
    {"module": "Agentes de IA", "name": "Agentes", "description": "Gestão de agentes de IA.", "is_active": True},
    {"module": "Agentes de IA", "name": "Prompts de Agentes", "description": "Prompts para agentes.", "is_active": True},
    {"module": "Agentes de IA", "name": "Configurações de agentes", "description": "Parâmetros de agentes.", "is_active": True},
    {"module": "Agentes de IA", "name": "Monitoramento de agentes", "description": "Monitoramento de agentes.", "is_active": True},
    {"module": "Agentes de IA", "name": "Testes de agentes", "description": "Testes de agentes.", "is_active": True},
    {"module": "IA e RAG", "name": "Gerenciamento RAG", "description": "Coleções e fontes RAG.", "is_active": True},
    {"module": "IA e RAG", "name": "Configurações RAG", "description": "Parâmetros de RAG.", "is_active": True},
    {"module": "IA e RAG", "name": "Gerenciamento de IA", "description": "Gerenciamento geral de IA.", "is_active": True},
    {"module": "IA e RAG", "name": "Configurações de IA", "description": "Configurações de IA.", "is_active": True},
    {"module": "Dashboard / Relatórios", "name": "Principal", "description": "Visão geral de KPIs.", "is_active": True},
    {"module": "Dashboard / Relatórios", "name": "Análises", "description": "Análises e gráficos.", "is_active": True},
    {"module": "Dashboard / Relatórios", "name": "Relatórios", "description": "Relatórios e exportações.", "is_active": True},
    {"module": "Gestão", "name": "Usuários", "description": "Gestão de usuários.", "is_active": True},
    {"module": "Gestão", "name": "Módulos", "description": "Gestão de módulos.", "is_active": True},
    {"module": "Gestão", "name": "Aplicações", "description": "Gestão de aplicações.", "is_active": True},
    {"module": "Gestão", "name": "Permissões", "description": "Controle de permissões.", "is_active": True},
    {"module": "Gestão", "name": "Gestão de Prompts", "description": "Gestão de prompts globais.", "is_active": True},
    {"module": "Gestão", "name": "Parâmetros Chatwoot", "description": "Configurar parâmetros Chatwoot.", "is_active": True},
    {"module": "Gestão", "name": "Backup/Logs", "description": "Backup e logs do sistema.", "is_active": True},
    {"module": "Gestão", "name": "Configurações do Sistema", "description": "Configurações gerais.", "is_active": True},
    {"module": "Testes", "name": "Gerenciamento dos Testes", "description": "Gerenciamento de suites de teste.", "is_active": True},
    {"module": "Testes", "name": "Execução de Testes", "description": "Execução de testes.", "is_active": True},
    {"module": "Conexões Externas", "name": "Conexão Chatwoot", "description": "Conectar ao Chatwoot.", "is_active": True},
]

modules = Table(
    "modules",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(255), unique=True, nullable=False),
    Column("description", Text, nullable=True),
    Column("is_active", Boolean, nullable=False, server_default=text("TRUE")),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    Column("data_hora_inclusao", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column(
        "data_hora_alteracao",
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),
)

applications = Table(
    "applications",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(255), unique=True, nullable=False),
    Column("description", Text, nullable=True),
    Column("is_active", Boolean, nullable=False, server_default=text("TRUE")),
    Column("module_id", Integer, ForeignKey("modules.id"), nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    Column("data_hora_inclusao", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column(
        "data_hora_alteracao",
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),
)

permissions = Table(
    "permissions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", Integer, nullable=False),
    Column("module_id", Integer, nullable=False),
    Column("application_id", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    Column("data_hora_inclusao", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column(
        "data_hora_alteracao",
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),
)


async def ensure_management_tables() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
        await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_modules_name ON modules (name)"))
        await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_applications_name ON applications (name)"))
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_permissions_user_app "
                "ON permissions (user_id, application_id)"
            )
        )
    # Seed módulos padrão (case-insensitive) usando sessionmaker para evitar problemas de commit
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        for module in _DEFAULT_MODULES:
            exists = await session.execute(
                select(modules.c.id).where(func.lower(modules.c.name) == module["name"].lower())
            )
            if not exists.first():
                await session.execute(
                    modules.insert().values(
                        name=module["name"],
                        description=module["description"],
                        is_active=True,
                    )
                )
        await session.commit()

        # Mapear módulos por nome para seeding das aplicações
        result = await session.execute(select(modules.c.id, modules.c.name))
        module_lookup = {row.name.lower(): row.id for row in result}

        for app in _DEFAULT_APPLICATIONS:
            module_id = module_lookup.get(app["module"].lower())
            if not module_id:
                continue
            exists = await session.execute(
                select(applications.c.id).where(func.lower(applications.c.name) == app["name"].lower())
            )
            if not exists.first():
                await session.execute(
                    applications.insert().values(
                        name=app["name"],
                        description=app["description"],
                        is_active=bool(app.get("is_active", True)),
                        module_id=module_id,
                    )
                )
        await session.commit()

    await ensure_audit_columns("modules")
    await ensure_audit_columns("applications")
    await ensure_audit_columns("permissions")


def _normalize_name(value: str, field: str = "nome") -> str:
    name = (value or "").strip()
    if not name:
        raise ValueError(f"Informe o {field}.")
    if len(name) > 255:
        raise ValueError(f"O {field} deve ter no máximo 255 caracteres.")
    return name


def _serialize(row: Any) -> dict[str, Any]:
    return dict(row)


async def list_modules(include_inactive: bool = True) -> list[dict[str, Any]]:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        query = select(modules).order_by(modules.c.name)
        if not include_inactive:
            query = query.where(modules.c.is_active.is_(True))
        result = await session.execute(query)
        return [_serialize(row) for row in result.mappings().all()]


async def create_module(name: str, description: str | None, is_active: bool = True) -> None:
    await ensure_management_tables()
    name_clean = _normalize_name(name, "nome do módulo")
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        exists = await session.execute(select(modules.c.id).where(func.lower(modules.c.name) == name_clean.lower()))
        if exists.first():
            raise ValueError("Módulo já existe.")
        await session.execute(
            modules.insert().values(
                name=name_clean,
                description=(description or "").strip() or None,
                is_active=bool(is_active),
            )
        )
        await session.commit()


async def update_module(
    module_id: int, *, name: str, description: str | None, is_active: bool = True
) -> None:
    await ensure_management_tables()
    name_clean = _normalize_name(name, "nome do módulo")
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        exists = await session.execute(
            select(modules.c.id).where(
                func.lower(modules.c.name) == name_clean.lower(),
                modules.c.id != module_id,
            )
        )
        if exists.first():
            raise ValueError("Módulo já existe.")
        result = await session.execute(
            modules.update()
            .where(modules.c.id == module_id)
            .values(
                name=name_clean,
                description=(description or "").strip() or None,
                is_active=bool(is_active),
            )
        )
        if result.rowcount == 0:
            raise ValueError("Módulo não encontrado.")
        await session.commit()


async def list_applications(include_inactive: bool = True) -> list[dict[str, Any]]:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        j = join(applications, modules, applications.c.module_id == modules.c.id)
        query = select(
            applications.c.id,
            applications.c.name,
            applications.c.description,
            applications.c.is_active,
            applications.c.module_id,
            modules.c.name.label("module_name"),
        ).select_from(j)
        if not include_inactive:
            query = query.where(applications.c.is_active.is_(True), modules.c.is_active.is_(True))
        query = query.order_by(applications.c.name)
        result = await session.execute(query)
        return [_serialize(row) for row in result.mappings().all()]


async def _get_module(session, module_id: int) -> dict[str, Any] | None:
    result = await session.execute(select(modules).where(modules.c.id == module_id))
    row = result.mappings().first()
    return _serialize(row) if row else None


async def create_application(
    name: str, description: str | None, module_id: int, is_active: bool = True
) -> None:
    await ensure_management_tables()
    name_clean = _normalize_name(name, "nome da aplicação")
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        module_row = await _get_module(session, module_id)
        if module_row is None:
            raise ValueError("Módulo não encontrado.")
        exists = await session.execute(
            select(applications.c.id).where(func.lower(applications.c.name) == name_clean.lower())
        )
        if exists.first():
            raise ValueError("Aplicação já existe.")

        await session.execute(
            applications.insert().values(
                name=name_clean,
                description=(description or "").strip() or None,
                is_active=bool(is_active),
                module_id=module_id,
            )
        )
        await session.commit()


async def update_application(
    application_id: int,
    *,
    name: str,
    description: str | None,
    module_id: int,
    is_active: bool = True,
) -> None:
    await ensure_management_tables()
    name_clean = _normalize_name(name, "nome da aplicação")
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        module_row = await _get_module(session, module_id)
        if module_row is None:
            raise ValueError("Módulo não encontrado.")
        exists = await session.execute(
            select(applications.c.id).where(
                func.lower(applications.c.name) == name_clean.lower(),
                applications.c.id != application_id,
            )
        )
        if exists.first():
            raise ValueError("Aplicação já existe.")

        result = await session.execute(
            applications.update()
            .where(applications.c.id == application_id)
            .values(
                name=name_clean,
                description=(description or "").strip() or None,
                is_active=bool(is_active),
                module_id=module_id,
            )
        )
        if result.rowcount == 0:
            raise ValueError("Aplicação não encontrada.")
        await session.commit()


async def list_permissions() -> list[dict[str, Any]]:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        j = (
            permissions.join(applications, permissions.c.application_id == applications.c.id)
            .join(modules, permissions.c.module_id == modules.c.id)
        )
        query = select(
            permissions.c.id,
            permissions.c.user_id,
            permissions.c.module_id,
            permissions.c.application_id,
            modules.c.name.label("module_name"),
            applications.c.name.label("application_name"),
        ).select_from(j)
        result = await session.execute(query)
        return [_serialize(row) for row in result.mappings().all()]


async def _get_application(session, application_id: int) -> dict[str, Any] | None:
    result = await session.execute(select(applications).where(applications.c.id == application_id))
    row = result.mappings().first()
    return _serialize(row) if row else None


async def create_permission(user_id: int, module_id: int, application_id: int) -> str | None:
    await ensure_users_table()
    await ensure_management_tables()
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        user = await get_user_by_id(user_id)
        if user is None:
            raise ValueError("Usuário não encontrado.")
        if user.get("role") == "ADMIN":
            return "Usuário ADMIN já possui acesso a todos os módulos e aplicações."

        module_row = await _get_module(session, module_id)
        if module_row is None:
            raise ValueError("Módulo não encontrado.")

        app_row = await _get_application(session, application_id)
        if app_row is None:
            raise ValueError("Aplicação não encontrada.")
        if app_row["module_id"] != module_id:
            raise ValueError("Aplicação não pertence ao módulo selecionado.")

        exists = await session.execute(
            select(permissions.c.id).where(
                and_(
                    permissions.c.user_id == user_id,
                    permissions.c.application_id == application_id,
                )
            )
        )
        if exists.first():
            raise ValueError("Permissão já existe para este usuário e aplicação.")

        await session.execute(
            permissions.insert().values(
                user_id=user_id,
                module_id=module_id,
                application_id=application_id,
            )
        )
        await session.commit()
    return None
