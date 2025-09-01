from __future__ import annotations
from typing import Dict, List, Set, Optional, Tuple
import re
import asyncio
import time  # Добавляем импорт time
from src.db.pool import fetch_all, fetch_one
from src.utils.logger import get_logger

logger = get_logger("reference_data")

# Кэш справочников (обновляется из БД)
_REFERENCE_CACHE = {
    "brands": {},
    "categories": {},
    "channels": {},
    "regions": {},
    "last_update": None
}

# Время жизни кэша (5 минут)
CACHE_TTL = 300

async def load_references_from_db():
    """Загружает актуальные справочники из базы данных."""
    try:
        # Загружаем бренды из таблицы products
        brands_query = """
        SELECT DISTINCT LOWER(brand) as brand_name
        FROM products 
        WHERE brand IS NOT NULL AND brand != ''
        ORDER BY brand_name
        """
        brands_result = await fetch_all(brands_query)
        
        # Загружаем категории из таблицы products
        categories_query = """
        SELECT DISTINCT 
            LOWER(category_1) as category_name,
            LOWER(category_group_1) as category_group
        FROM products 
        WHERE category_1 IS NOT NULL AND category_1 != ''
        ORDER BY category_name
        """
        categories_result = await fetch_all(categories_query)
        
        # Загружаем каналы сбыта из таблицы profit
        channels_query = """
        SELECT DISTINCT LOWER(channel) as channel_name
        FROM profit 
        WHERE channel IS NOT NULL AND channel != ''
        ORDER BY channel_name
        """
        channels_result = await fetch_all(channels_query)
        
        # Загружаем регионы из таблицы clients
        regions_query = """
        SELECT DISTINCT LOWER(region) as region_name
        FROM clients 
        WHERE region IS NOT NULL AND region != ''
        ORDER BY region_name
        """
        regions_result = await fetch_all(regions_query)
        
        # Обновляем кэш
        _REFERENCE_CACHE["brands"] = {
            row["brand_name"]: "brand" for row in brands_result
        }
        
        _REFERENCE_CACHE["categories"] = {}
        for row in categories_result:
            if row["category_name"]:
                _REFERENCE_CACHE["categories"][row["category_name"]] = "category"
            if row["category_group"]:
                _REFERENCE_CACHE["categories"][row["category_group"]] = "category"
        
        _REFERENCE_CACHE["channels"] = {
            row["channel_name"]: "channel" for row in channels_result
        }
        
        _REFERENCE_CACHE["regions"] = {
            row["region_name"]: "region" for row in regions_result
        }
        
        _REFERENCE_CACHE["last_update"] = time.time()
        
        logger.info(f"✅ Справочники обновлены: {len(_REFERENCE_CACHE['brands'])} брендов, "
                   f"{len(_REFERENCE_CACHE['categories'])} категорий, "
                   f"{len(_REFERENCE_CACHE['channels'])} каналов, "
                   f"{len(_REFERENCE_CACHE['regions'])} регионов")
        
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки справочников из БД: {e}")
        # В случае ошибки используем базовые справочники
        _load_fallback_references()

def _load_fallback_references():
    """Загружает базовые справочники в случае ошибки БД."""
    _REFERENCE_CACHE["brands"] = {
        "чабан": "brand", "молочный": "brand", "сырный": "brand"
    }
    _REFERENCE_CACHE["categories"] = {
        "молочная продукция": "category", "сыр": "category", "мясо": "category"
    }
    _REFERENCE_CACHE["channels"] = {
        "розница": "channel", "опт": "channel", "интернет": "channel"
    }
    _REFERENCE_CACHE["regions"] = {
        "москва": "region", "спб": "region", "краснодар": "region"
    }
    _REFERENCE_CACHE["last_update"] = time.time()
    logger.warning("⚠️ Используются базовые справочники")

def _is_cache_expired():
    """Проверяет, истек ли срок действия кэша."""
    if _REFERENCE_CACHE["last_update"] is None:
        return True
    current_time = time.time()
    return (current_time - _REFERENCE_CACHE["last_update"]) > CACHE_TTL

async def ensure_references_loaded():
    """Убеждается, что справочники загружены и актуальны."""
    if _is_cache_expired():
        await load_references_from_db()

async def force_refresh_references():
    """Принудительно обновляет справочники из БД."""
    _REFERENCE_CACHE["last_update"] = None
    await load_references_from_db()

def get_references_stats():
    """Возвращает статистику по загруженным справочникам."""
    return {
        "brands_count": len(_REFERENCE_CACHE["brands"]),
        "categories_count": len(_REFERENCE_CACHE["categories"]),
        "channels_count": len(_REFERENCE_CACHE["channels"]),
        "regions_count": len(_REFERENCE_CACHE["regions"]),
        "last_update": _REFERENCE_CACHE["last_update"],
        "cache_expired": _is_cache_expired()
    }

async def extract_entities(text: str) -> Dict[str, List[str]]:
    """
    Извлекает сущности из текста и возвращает их по типам.
    
    Args:
        text: Входной текст для анализа
        
    Returns:
        Словарь с типами сущностей и их значениями
    """
    # Убеждаемся, что справочники загружены
    await ensure_references_loaded()
    
    text_lower = text.lower()
    entities = {
        "brands": [],
        "categories": [], 
        "channels": [],
        "regions": [],
        "unknown": []
    }
    
    # Проверяем бренды
    for brand, entity_type in _REFERENCE_CACHE["brands"].items():
        if brand in text_lower:
            entities["brands"].append(brand)
    
    # Проверяем категории
    for category, entity_type in _REFERENCE_CACHE["categories"].items():
        if category in text_lower:
            entities["categories"].append(category)
    
    # Проверяем каналы сбыта
    for channel, entity_type in _REFERENCE_CACHE["channels"].items():
        if channel in text_lower:
            entities["channels"].append(channel)
    
    # Проверяем регионы
    for region, entity_type in _REFERENCE_CACHE["regions"].items():
        if region in text_lower:
            entities["regions"].append(region)
    
    return entities

def get_entity_context(entities: Dict[str, List[str]]) -> str:
    """
    Формирует контекст для AI на основе найденных сущностей.
    
    Args:
        entities: Словарь с найденными сущностями
        
    Returns:
        Строка с контекстом для AI
    """
    context_parts = []
    
    if entities["brands"]:
        context_parts.append(f"Бренды: {', '.join(entities['brands'])}")
    
    if entities["categories"]:
        context_parts.append(f"Категории: {', '.join(entities['categories'])}")
    
    if entities["channels"]:
        context_parts.append(f"Каналы сбыта: {', '.join(entities['channels'])}")
    
    if entities["regions"]:
        context_parts.append(f"Регионы: {', '.join(entities['regions'])}")
    
    if context_parts:
        return " | ".join(context_parts)
    
    return ""

async def enrich_prompt_with_entities(user_text: str) -> str:
    """
    Обогащает промпт пользователя информацией о найденных сущностях.
    
    Args:
        user_text: Исходный текст пользователя
        
    Returns:
        Обогащенный текст с контекстом
    """
    entities = await extract_entities(user_text)
    context = get_entity_context(entities)
    
    if context:
        return f"{user_text}\n\n[Контекст: {context}]"
    
    return user_text
