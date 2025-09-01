from __future__ import annotations
import os
import asyncio
from typing import Optional, Dict, Any
import asyncpg
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Глобальный пул соединений
_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    """Получить или создать пул соединений"""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            host=os.getenv("PG_HOST", "localhost"),
            port=int(os.getenv("PG_PORT", "5432")),
            database=os.getenv("PG_DB", "milk"),
            user=os.getenv("PG_USER"),
            password=os.getenv("PG_PASSWORD"),
            ssl=os.getenv("PG_SSLMODE", "prefer") == "require",
            min_size=5,
            max_size=20,
            command_timeout=60
        )
    return _pool


async def close_pool():
    """Закрыть пул соединений"""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def fetch_one(query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
    """Выполнить запрос и вернуть одну строку"""
    from src.utils.logger import get_logger
    logger = get_logger("db.pool")
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(query, *params)
                return dict(row) if row else None
        except Exception as e:
            logger.warning(f"⚠️ Попытка {attempt + 1}/{max_retries} для fetch_one: {e}")
            if attempt == max_retries - 1:
                logger.error(f"❌ Все попытки fetch_one исчерпаны: {e}")
                raise
            await asyncio.sleep(0.1 * (attempt + 1))  # Экспоненциальная задержка


async def fetch_all(query: str, params: tuple = ()) -> list[Dict[str, Any]]:
    """Выполнить запрос и вернуть все строки"""
    from src.utils.logger import get_logger
    logger = get_logger("db.pool")
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.warning(f"⚠️ Попытка {attempt + 1}/{max_retries} для fetch_all: {e}")
            if attempt == max_retries - 1:
                logger.error(f"❌ Все попытки fetch_all исчерпаны: {e}")
                raise
            await asyncio.sleep(0.1 * (attempt + 1))  # Экспоненциальная задержка


async def execute_returning(query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
    """Выполнить запрос с возвратом результата"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *params)
        return dict(row) if row else None


async def execute(query: str, params: tuple = ()) -> None:
    """Выполнить запрос без возврата результата"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(query, *params)
