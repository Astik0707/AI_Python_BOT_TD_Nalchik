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
    "clients": {},
    "managers": {},
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
        
        # Загружаем клиентов (публичные/юридические названия)
        clients_query = """
        SELECT DISTINCT LOWER(COALESCE(NULLIF(public_name,''), client_name)) AS client_name
        FROM clients
        WHERE COALESCE(NULLIF(public_name,''), client_name) IS NOT NULL
        ORDER BY client_name
        """
        clients_result = await fetch_all(clients_query)

        # Загружаем менеджеров из sales_representatives и union c profit.manager
        managers_result = []
        try:
            managers_query = """
            SELECT DISTINCT LOWER(full_name) AS manager_name
            FROM sales_representatives
            WHERE full_name IS NOT NULL AND full_name != ''
            """
            managers_result = await fetch_all(managers_query)
        except Exception:
            managers_result = []
        profit_managers_result = []
        try:
            profit_mgr_query = """
            SELECT DISTINCT LOWER(manager) AS manager_name
            FROM profit
            WHERE manager IS NOT NULL AND manager != ''
            """
            profit_managers_result = await fetch_all(profit_mgr_query)
        except Exception:
            profit_managers_result = []
        # Объединяем и нормализуем
        manager_names: Set[str] = set()
        for row in managers_result:
            if row.get("manager_name"):
                manager_names.add(row["manager_name"])
        for row in profit_managers_result:
            if row.get("manager_name"):
                manager_names.add(row["manager_name"])
        
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
        
        _REFERENCE_CACHE["clients"] = {
            row["client_name"]: "client" for row in clients_result
        }
        
        _REFERENCE_CACHE["managers"] = {name: "manager" for name in manager_names}
        
        _REFERENCE_CACHE["last_update"] = time.time()
        
        logger.info(
            f"✅ Справочники обновлены: {len(_REFERENCE_CACHE['brands'])} брендов, "
            f"{len(_REFERENCE_CACHE['categories'])} категорий, "
            f"{len(_REFERENCE_CACHE['channels'])} каналов, "
            f"{len(_REFERENCE_CACHE['regions'])} регионов, "
            f"{len(_REFERENCE_CACHE['clients'])} клиентов, "
            f"{len(_REFERENCE_CACHE['managers'])} менеджеров"
        )
        
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
        "clients_count": len(_REFERENCE_CACHE["clients"]),
        "managers_count": len(_REFERENCE_CACHE["managers"]),
        "last_update": _REFERENCE_CACHE["last_update"],
        "cache_expired": _is_cache_expired()
    }

def _norm(s: str) -> str:
    return (s or "").lower().replace("ё", "е")


def _has_word(text: str, phrase: str) -> bool:
    if not phrase:
        return False
    try:
        pattern = r"\b" + re.escape(phrase) + r"\b"
        return re.search(pattern, text, flags=re.IGNORECASE) is not None
    except re.error:
        return phrase in text


# ---------------- Heuristics for Russian token matching (surname endings) ----------------

_ENDINGS = [
    "ами", "ями", "ями", "ях", "ях", "ами", "ями",
    "ого", "ему", "ому", "ыми", "ими",
    "ой", "ом", "ым", "ем",
    "ев", "ов",  # plural possessive sometimes appears
    "а", "я", "у", "е", "ы", "и",
]


def _tokenize(text: str) -> List[str]:
    try:
        return re.findall(r"[a-zA-Zа-яА-ЯёЁ]+", text or "")
    except re.error:
        return (text or "").split()


def _stem_simple(token: str) -> str:
    t = _norm(token)
    for suf in _ENDINGS:
        if t.endswith(suf) and len(t) > len(suf) + 2:
            return t[: -len(suf)]
    return t


def _tokens_match_approx(a: str, b: str) -> bool:
    if not a or not b:
        return False
    aa = _stem_simple(a)
    bb = _stem_simple(b)
    if aa == bb:
        return True
    # Allow contains when short (>=4 chars) after stemming
    if len(aa) >= 4 and (aa in bb or bb in aa):
        return True
    return False


def resolve_manager_name_from_text(text: str) -> Optional[str]:
    """Attempt to resolve a manager full name from free text using cached managers.
    Returns lower-cased full name if uniquely resolved, else None.
    """
    text_tokens = _tokenize(text or "")
    stems = [_stem_simple(t) for t in text_tokens]
    if not stems:
        return None
    candidates: List[str] = []
    for name in _REFERENCE_CACHE.get("managers", {}).keys():
        parts = [p for p in (name or "").split() if p]
        if not parts:
            continue
        surname = parts[0]
        if any(_tokens_match_approx(surname, st) for st in stems):
            candidates.append(name)
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    # Try to disambiguate by first name token
    filtered: List[str] = []
    for cand in candidates:
        parts = [p for p in cand.split() if p]
        first = parts[1] if len(parts) >= 2 else ""
        if first and any(_tokens_match_approx(first, st) for st in stems):
            filtered.append(cand)
    if len(filtered) == 1:
        return filtered[0]
    return None


async def extract_entities(text: str) -> Dict[str, List[str]]:
    """
    Извлекает сущности из текста и возвращает их по типам.
    """
    await ensure_references_loaded()

    text_lower = _norm(text)
    entities = {
        "brands": [],
        "categories": [],
        "channels": [],
        "regions": [],
        "managers": [],
        "clients": [],
        "unknown": []
    }

    # Бренды — по границам слов, чтобы "динамика" не совпадала с "мика"
    for brand, entity_type in _REFERENCE_CACHE["brands"].items():
        b = _norm(brand)
        if _has_word(text_lower, b):
            entities["brands"].append(b)

    # Категории
    for category, entity_type in _REFERENCE_CACHE["categories"].items():
        c = _norm(category)
        if _has_word(text_lower, c):
            entities["categories"].append(c)

    # Каналы
    for channel, entity_type in _REFERENCE_CACHE["channels"].items():
        ch = _norm(channel)
        if _has_word(text_lower, ch):
            entities["channels"].append(ch)

    # Регионы
    for region, entity_type in _REFERENCE_CACHE["regions"].items():
        r = _norm(region)
        if _has_word(text_lower, r):
            entities["regions"].append(r)

    # Менеджеры (ФИО целиком или части через границы слов) + грубая нормализация падежей
    tokens = _tokenize(text)
    stems = [_stem_simple(t) for t in tokens]
    for manager, entity_type in _REFERENCE_CACHE["managers"].items():
        m = _norm(manager)
        # прямое точное совпадение слова
        if _has_word(text_lower, m):
            entities["managers"].append(m)
            continue
        # по фамилии/части с учётом стемминга
        parts = [p for p in re.split(r"\s+", m) if p]
        if parts:
            surname = parts[0]
            if any(_tokens_match_approx(surname, st) for st in stems):
                entities["managers"].append(m)

    # Клиенты
    for client, entity_type in _REFERENCE_CACHE["clients"].items():
        cl = _norm(client)
        if _has_word(text_lower, cl):
            entities["clients"].append(cl)

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
    if entities["managers"]:
        context_parts.append(f"Менеджеры: {', '.join(entities['managers'])}")
    if entities["clients"]:
        context_parts.append(f"Клиенты: {', '.join(entities['clients'])}")

    # Возвращаем итоговую строку контекста
    if context_parts:
        return " | ".join(context_parts)
    return ""

def analyze_entities(text: str) -> Tuple[Dict[str, List[str]], List[str]]:
    """Возвращает сущности и список неоднозначных токенов (совпали в нескольких типах)."""
    import itertools
    ents = asyncio.get_event_loop().run_until_complete(extract_entities(text)) if asyncio.get_event_loop().is_running() is False else {}
    if not ents:
        # fallback sync call
        # In async contexts, caller should use extract_entities directly
        return {"brands":[],"categories":[],"channels":[],"regions":[],"managers":[],"clients":[],"unknown":[]}, []
    token_to_types: Dict[str, Set[str]] = {}
    for t in ["brands","categories","channels","regions","managers","clients"]:
        for val in ents.get(t, []):
            token_to_types.setdefault(val, set()).add(t)
    ambiguous = [tok for tok, types in token_to_types.items() if len(types) > 1]
    return ents, ambiguous
    
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
