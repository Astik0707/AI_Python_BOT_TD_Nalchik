from __future__ import annotations
import re
from typing import Optional
from src.utils.logger import get_logger
import os

logger = get_logger("validation")


def validate_sql_query(query: str) -> bool:
    """Валидация SQL-запроса на предмет опасных операций"""
    if not query or not query.strip():
        return False
    
    # Приводим к нижнему регистру для проверки
    query_lower = query.lower().strip()
    
    # Запрещённые операции
    dangerous_operations = [
        'drop', 'delete', 'truncate', 'alter', 'create', 'insert', 'update',
        'grant', 'revoke', 'backup', 'restore', 'exec', 'execute'
    ]
    
    # Проверяем на наличие опасных операций
    for operation in dangerous_operations:
        if operation in query_lower:
            logger.warning(f"Dangerous SQL operation detected: {operation}")
            return False
    
    # Проверяем на множественные запросы
    if ';' in query and query.count(';') > 1:
        logger.warning("Multiple SQL statements detected")
        return False
    
    return True


def validate_email(email: str) -> bool:
    """Валидация email адреса"""
    if not email or not email.strip():
        return False
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))


def validate_file_path(path: str) -> bool:
    """Валидация пути к файлу"""
    if not path or not path.strip():
        return False
    
    # Проверяем на попытки path traversal
    normalized_path = os.path.normpath(path)
    if '..' in normalized_path or normalized_path.startswith('/'):
        return False
    
    return True


def sanitize_filename(filename: str) -> str:
    """Санитизация имени файла"""
    if not filename:
        return ""
    
    # Удаляем опасные символы
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Ограничиваем длину
    if len(filename) > 255:
        filename = filename[:255]
    
    return filename.strip()


def validate_text_length(text: str, max_length: int = 4096) -> bool:
    """Валидация длины текста"""
    return text and len(text.strip()) <= max_length


def validate_chat_id(chat_id: int) -> bool:
    """Валидация ID чата"""
    return isinstance(chat_id, int) and chat_id != 0


def validate_user_id(user_id: Optional[int]) -> bool:
    """Валидация ID пользователя"""
    return user_id is None or (isinstance(user_id, int) and user_id > 0)
