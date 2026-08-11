"""Bazaga ulanish va sessiya."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import DATABASE_URL
from app.models import Base

# Neon (Postgres) TLS talab qiladi — asyncpg uchun ssl'ni aniq beramiz.
_connect_args = {"ssl": True} if DATABASE_URL.startswith("postgresql+asyncpg") else {}

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=280,  # Neon bo'sh ulanishlarni uzadi
    connect_args=_connect_args,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


# Yetishmayotgan ustunlar: {jadval: {ustun: DDL turi}}.
# `create_all` mavjud jadvalga yangi ustun QO'SHMAYDI — shuning uchun
# kichik o'zgarishlar shu yerda qo'lda yuritiladi. Alembic bu loyiha
# hajmi uchun ortiqcha: yiliga bir-ikki ustun qo'shiladi.
_MIGRATIONS: dict[str, dict[str, str]] = {
    "chat_messages": {"archived_at": "TIMESTAMP"},
}


def _apply_migrations(conn) -> None:
    inspector = inspect(conn)
    tables = set(inspector.get_table_names())
    for table, columns in _MIGRATIONS.items():
        if table not in tables:
            continue  # create_all uni to'liq yaratgan
        existing = {c["name"] for c in inspector.get_columns(table)}
        for column, ddl in columns.items():
            if column not in existing:
                conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_apply_migrations)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency."""
    async with SessionLocal() as session:
        yield session
