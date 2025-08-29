from __future__ import annotations
from src.db.pool import fetch_one


async def check_authorized_chat(chat_id: int) -> bool:
    """Проверить авторизацию чата"""
    try:
        row = await fetch_one("SELECT EXISTS(SELECT 1 FROM bot_autorized_chats WHERE chat_id = $1) AS allowed;", (chat_id,))
        return bool(row and row.get("allowed"))
    except Exception:
        # В случае ошибки БД - отказываем в доступе
        return False
