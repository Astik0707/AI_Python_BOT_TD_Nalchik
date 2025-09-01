from __future__ import annotations
from src.db.pool import fetch_one


async def check_authorized_chat(chat_id: int) -> bool:
    """Проверить авторизацию чата"""
    from src.utils.logger import get_logger
    logger = get_logger("auth")
    
    logger.info(f"🔐 Проверка авторизации для chat_id: {chat_id}")
    
    try:
        # Просто проверяем существование записи в таблице
        logger.info(f"🔍 Выполняю SQL запрос для chat_id: {chat_id}")
        row = await fetch_one("SELECT chat_id FROM bot_autorized_chats WHERE chat_id = $1;", (chat_id,))
        
        logger.info(f"📋 Результат SQL запроса: {row}")
        
        is_authorized = bool(row)
        logger.info(f"✅ Результат авторизации для chat_id {chat_id}: {is_authorized}")
        
        return is_authorized  # Если запись найдена - доступ разрешен
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке авторизации для chat_id {chat_id}: {e}")
        # В случае ошибки БД - отказываем в доступе
        return False
