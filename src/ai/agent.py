# src/ai/agent.py
from __future__ import annotations

import os
import json
from typing import List, Dict, Any, Optional

from src.utils.logger import get_logger
from src.utils.memory import append_message
from src.db.sql import execute_sql

from .models import AgentResult
from .openai_client import get_client
from .classifier import requires_database
from .messages import build_messages  # уже включает текущую дату из БД
from .sql_tools import strict_retry_sql_query, validate_and_sanitize_sql
from .renderer import render_rows, render_no_data, render_text_info

logger = get_logger("ai.agent")


async def run_ai_for_text(chat_id: int, text: str, user_id: Optional[int] = None, **kwargs) -> AgentResult:
    """Тонкий оркестратор: LLM -> (sql_query) -> DB -> красивый HTML.
    user_id оставлен для обратной совместимости с обработчиками, не используется.
    """
    if not text or not text.strip():
        return AgentResult(output="Пожалуйста, введите текст для обработки.")

    need_db = requires_database(text)
    messages = await build_messages(text, chat_id)

    client = get_client()
    model = os.environ.get("OPENAI_MODEL_CHAT", "gpt-4.1")

    # 1) Первый проход: строгий JSON (output/send_excel/table_data/sql_query)
    try:
        r = await client.chat.completions.create(
            model=model,
            messages=messages + [{
                "role": "system",
                "content": "Если нужна БД — ОБЯЗАТЕЛЬНО верни sql_query в JSON. Не добавляй лишних полей."
            }],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        data = json.loads((r.choices[0].message.content if r.choices else "{}") or "{}")
        logger.info(f"✅ AI ответ получен. send_excel={data.get('send_excel')}, send_card={data.get('send_card')}")
    except Exception as e:
        logger.error(f"AI request error: {e}")
        return AgentResult(
            output="<b>Ошибка при обращении к AI.</b> Попробуйте позже.",
            send_excel=False,
            table_data=[],
            sql_query=None,
        )

    output = (data.get("output") or "").strip()
    sql_query: Optional[str] = data.get("sql_query") or None

    # 2) Если БД нужна, но sql_query нет — жёстко «дожимаем»
    if need_db and not sql_query:
        logger.warning("🚨 SQL REQUIRED BUT MISSING — STRICT RETRY")
        sql_query = await strict_retry_sql_query(messages, model)
        if not sql_query:
            return AgentResult(
                output=(
                    "<b>Нужен SQL-запрос для получения данных, но сформировать его не удалось.</b>\n"
                    "Уточните, пожалуйста, период, метрику и фильтры (бренд/менеджер/регион и т.п.)."
                ),
                send_excel=False,
                table_data=[],
                sql_query=None,
            )

    # 3) Ветка без БД (small talk/служебные ответы)
    if not need_db:
        if not output:
            output = "Хм… Не совсем понял запрос. Сформулируйте, пожалуйста, период и метрику (например: «выручка по брендам за февраль»)."
        res = render_text_info(output)
        await _remember(chat_id, text, res.output)
        return res

    # 4) Есть sql_query → валидируем/санитизируем → выполняем в БД
    assert sql_query is not None
    val = await validate_and_sanitize_sql(sql_query)
    if not val.is_valid:
        # показываем первую ошибку (например, «Менеджер не найден»)
        err = val.errors[0] if val.errors else "Некорректный SQL-запрос."
        res = render_text_info(f"<b>{err}</b>")
        await _remember(chat_id, text, res.output)
        return res

    sanitized_sql = val.sanitized_sql
    try:
        logger.info("🚀 CALLING DATABASE WITH SQL QUERY...")
        rows = await execute_sql(sanitized_sql)
        logger.info(f"✅ DATABASE RESPONSE: {len(rows) if isinstance(rows, list) else 'unknown'} rows received")
    except Exception as e:
        logger.error(f"SQL execution error: {e}")
        res = render_text_info("<b>Пока не могу получить данные из базы.</b>")
        await _remember(chat_id, text, res.output)
        return res

    if not rows:
        res = render_no_data(sanitized_sql)
        await _remember(chat_id, text, res.output)
        return res

    # 5) Красивый HTML как в n8n (единицы/тысячи/запятые), Excel при больших выборках
    result = render_rows(rows, text, existing_title=None, sql_query=sanitized_sql)

    # Мягко показываем предупреждения валидатора (если были) — внизу мелким текстом
    if val.warnings:
        warn = " ".join(val.warnings)
        result.output = result.output + f"\n\n<i>{warn}</i>"

    await _remember(chat_id, text, result.output)
    return result


async def _remember(chat_id: int, user_text: str, assistant_text: str) -> None:
    """Короткий лог общения в память."""
    try:
        await append_message(chat_id, "user", user_text)
        await append_message(chat_id, "assistant", assistant_text)
    except Exception:
        pass


async def process_chart_edit(chat_id: int, text: str, saved_config: Dict[str, Any]) -> AgentResult:
    """Редактирование графиков пока не поддерживается в этой ветке."""
    return AgentResult(
        output="<b>Редактирование графиков пока не реализовано.</b>",
        send_excel=False,
        table_data=[],
        sql_query=None,
    )
