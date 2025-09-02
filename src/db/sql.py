from __future__ import annotations
from typing import List, Dict, Any
from src.db.pool import fetch_all
from src.db.sql_guard import guard_sql
import time
import logging


async def execute_sql(query: str) -> List[Dict[str, Any]]:
    """Выполнить SQL-запрос и вернуть результаты"""
    logger = logging.getLogger("sql")
    
    # Логируем начало выполнения запроса
    logger.info(f"🚀 EXECUTING SQL QUERY: {query[:200]}{'...' if len(query) > 200 else ''}")
    
    try:
        start = time.perf_counter()
        # Удаляем ведущие комментарии перед валидацией (чтобы guard не отклонял SELECT)
        q = (query or "")
        q = q.lstrip()
        changed = True
        while changed:
            changed = False
            if q.startswith("--"):
                nl = q.find("\n")
                q = q[nl + 1:] if nl != -1 else ""
                q = q.lstrip()
                changed = True
            elif q.startswith("/*"):
                end = q.find("*/")
                if end != -1:
                    q = q[end + 2:]
                    q = q.lstrip()
                    changed = True
        safe_query = guard_sql(q)
        rows = await fetch_all(safe_query)
        dur_ms = int((time.perf_counter() - start) * 1000)
        
        # Детальное логирование результата
        logger.info(f"✅ SQL QUERY SUCCESS: {dur_ms}ms, {len(rows)} rows returned")
        
        # Логируем первые несколько строк для отладки
        if rows and len(rows) > 0:
            first_row = rows[0]
            logger.info(f"📊 FIRST ROW DATA: {dict(first_row)}")
            if len(rows) > 1:
                logger.info(f"📊 TOTAL ROWS: {len(rows)} (showing first row only)")
        
        return rows
    except Exception as e:
        # Детальное логирование ошибки
        logger.error(f"❌ SQL QUERY FAILED: {e}")
        logger.error(f"❌ FAILED QUERY: {query}")
        return []
