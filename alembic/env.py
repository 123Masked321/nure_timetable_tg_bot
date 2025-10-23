import asyncio
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# Это Alembic Config object, который предоставляет доступ к значениям в .ini файле
config = context.config

# Интерпретируем ini-файл для Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Здесь нужно импортировать MetaData ваших моделей
# Это позволит Alembic автоматически генерировать миграции
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from os import getenv
DATABASE_URL = getenv("DATABASE_URL")

config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Добавляем корневую директорию проекта в путь, чтобы можно было импортировать модели
sys.path.append(str(Path(__file__).parent.parent))

from database.models import Base

target_metadata = Base.metadata


# Другие значения из alembic.ini, определенные для env.py
# Здесь мы можем получить URL базы данных из alembic.ini
# Например:
# from config.settings import DATABASE_URL
# config.set_main_option("sqlalchemy.url", DATABASE_URL)
# Так как вы используете асинхронный драйвер, это нужно будет настроить
# в alembic.ini или здесь.

def run_migrations_offline() -> None:
    """Запускает миграции в 'offline' режиме."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """Функция для выполнения миграций с асинхронным подключением."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Запускает миграции в 'online' режиме, используя асинхронный движок."""
    connectable = config.attributes.get("connection", None)
    if connectable is None:
        # Получаем URL из alembic.ini
        url = config.get_main_option("sqlalchemy.url")
        connectable = create_async_engine(
            url,
            poolclass=pool.NullPool,
        )

    async def run_async_migrations():
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
        await connectable.dispose()

    # 🔧 Вот тут — исправление:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

