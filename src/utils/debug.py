from __future__ import annotations
import os
from typing import Optional
from telegram.ext import ContextTypes
import redis.asyncio as redis

_redis: Optional[redis.Redis] = None


def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=int(os.getenv("REDIS_DB", "0")),
            password=os.getenv("REDIS_PASSWORD") or None,
            decode_responses=True,
        )
    return _redis


def _key(chat_id: int) -> str:
    return f"chat_debug:{chat_id}"


async def set_debug(chat_id: int, enabled: bool) -> None:
    r = _get_redis()
    if enabled:
        await r.set(_key(chat_id), "1", ex=7*24*3600)
    else:
        await r.delete(_key(chat_id))


async def is_debug(chat_id: int) -> bool:
    r = _get_redis()
    return bool(await r.exists(_key(chat_id)))


async def tg_debug(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str) -> None:
    """Отправить диагностическое сообщение в чат, если режим включён."""
    if await is_debug(chat_id):
        try:
            await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
        except Exception:
            pass
