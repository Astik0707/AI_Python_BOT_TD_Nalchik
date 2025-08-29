from __future__ import annotations
import os
from typing import List, Dict
import json
import asyncio
import redis.asyncio as redis

_redis: redis.Redis | None = None


def get_redis() -> redis.Redis:
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


def _chat_key(chat_id: int) -> str:
    return f"chat_history:{chat_id}"


async def append_message(chat_id: int, role: str, content: str, max_messages: int = 20) -> None:
    r = get_redis()
    item = json.dumps({"role": role, "content": content})
    await r.rpush(_chat_key(chat_id), item)
    await r.ltrim(_chat_key(chat_id), -max_messages, -1)
    # TTL на 7 дней
    await r.expire(_chat_key(chat_id), 7 * 24 * 3600)


async def get_history(chat_id: int, limit: int = 10) -> List[Dict[str, str]]:
    r = get_redis()
    items = await r.lrange(_chat_key(chat_id), -limit, -1)
    history: List[Dict[str, str]] = []
    for it in items:
        try:
            history.append(json.loads(it))
        except Exception:
            continue
    return history


async def clear_history(chat_id: int) -> None:
    r = get_redis()
    await r.delete(_chat_key(chat_id))
