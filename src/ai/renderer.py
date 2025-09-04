# src/ai/renderer.py
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from src.utils.formatter import build_html_from_rows
from src.utils.html_sanitize import sanitize_html
from .models import AgentResult

# Порог, после которого предлагаем Excel
EXCEL_THRESHOLD = int(os.getenv("EXCEL_THRESHOLD", "30"))


def _is_short_phrase(text: str) -> bool:
    """Эвристика: короткие/служебные фразы не используем как заголовок."""
    if not text:
        return True
    t = text.strip().lower()
    short = {
        "в кг", "кг", "вес", "по весу",
        "да", "нет", "это", "то", "все", "всего", "еще", "ещё",
        "покажи", "дай", "нужно", "хочу", "мне", "мне нужно",
        "отлично", "хорошо", "плохо", "нормально", "давайте",
        "пожалуйста", "спасибо", "благодарю", "извините"
    }
    if t in short:
        return True
    return len(t) < 10


def _title_from_user(text: str) -> Optional[str]:
    """Делаем заголовок из пользовательского текста, если он осмысленный."""
    if not text or _is_short_phrase(text):
        return None
    t = text.strip().rstrip(":")
    if not t:
        return None
    return f"<b>{t[0].upper() + t[1:]}</b>"


def render_rows(
    rows: List[Dict[str, Any]],
    user_text: str,
    *,
    existing_title: Optional[str] = None,
    sql_query: Optional[str] = None,
) -> AgentResult:
    """
    Главный рендерер для ответов из БД:
    - строит аккуратный HTML через formatter.build_html_from_rows,
    - санитизирует,
    - добавляет table_data и флаг send_excel по порогу.
    """
    if not rows:
        return render_no_data(sql_query)

    title = existing_title or _title_from_user(user_text)
    html = build_html_from_rows(rows, existing_title=title)
    html = sanitize_html(html)

    send_excel = len(rows) > EXCEL_THRESHOLD
    return AgentResult(
        output=html,
        send_excel=send_excel,
        table_data=rows if send_excel else None,
        sql_query=sql_query,
    )


def render_no_data(sql_query: Optional[str]) -> AgentResult:
    """Стандартный ответ при пустой выборке."""
    return AgentResult(
        output="<b>Нет данных по заданным условиям.</b>\nМогу отправить полный список в Excel — напишите: в excel",
        send_excel=False,
        table_data=[],
        sql_query=sql_query,
    )


def render_text_info(text: str) -> AgentResult:
    """
    Рендер для «разговорных»/служебных ответов без БД:
    - санитизируем,
    - обеспечиваем наличие заголовка.
    """
    body = sanitize_html(text or "")
    if not body.strip():
        body = "Хм… Не совсем понял запрос. Сформулируйте, пожалуйста, период и метрику."
    if not body.lstrip().startswith("<b>"):
        body = f"<b>Информация</b>\n\n{body}"
    return AgentResult(output=body)
