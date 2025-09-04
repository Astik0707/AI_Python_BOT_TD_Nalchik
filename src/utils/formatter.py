from __future__ import annotations
from typing import Any, Dict, List, Optional, Sequence, Tuple
import datetime as _dt
import os
from decimal import Decimal
import re

# ВАЖНО: используем корректный модуль sanitize_html
from src.utils.html_sanitize import sanitize_html


# =========================
# ЧИСЛА И ЕДИНИЦЫ
# =========================

def _to_float(value: Any) -> Optional[float]:
    """Безопасно приводит значение к float. Поддерживает int/float/Decimal/str с пробелами и запятыми.
    Возвращает None, если не похоже на число.
    """
    if value is None:
        return None
    if isinstance(value, float):
        return value
    if isinstance(value, int):
        return float(value)
    if isinstance(value, Decimal):
        try:
            return float(value)
        except Exception:
            return None
    try:
        s = str(value).strip().replace("\u00A0", " ")
        s = s.replace(" ", "").replace(",", ".")
        return float(s)
    except Exception:
        return None


def format_number_ru(value: Any) -> str:
    """Формат: 12 345,67; для целых — 12 345 (без ,00). Если не число — исходная строка."""
    num = _to_float(value)
    if num is None:
        return str(value)

    whole, frac = f"{num:.2f}".split(".")
    groups: List[str] = []
    for i in range(len(whole), 0, -3):
        start = max(i - 3, 0)
        groups.append(whole[start:i])
    whole_spaced = " ".join(reversed(groups))
    return whole_spaced if frac == "00" else f"{whole_spaced},{frac}"


def with_unit(value: Any, unit: str) -> str:
    """Форматирует число + добавляет единицу, если она задана."""
    formatted = format_number_ru(value)
    return f"{formatted}{unit}" if unit else formatted


def unit_for_key(value_key_lower: Optional[str]) -> str:
    """Определяет единицу измерения по названию ключа."""
    if not value_key_lower:
        return ""
    k = value_key_lower

    # Деньги
    if ("revenue" in k) or ("sum" in k) or ("amount" in k) or ("руб" in k) or ("₽" in k) or ("выручк" in k) or ("return" in k):
        return " ₽"

    # Вес
    if ("weight" in k) or ("kg" in k) or ("вес" in k) or ("кг" in k):
        return " кг"

    # Количество
    if ("quantity" in k) or ("qty" in k) or ("колич" in k) or ("шт" in k):
        return " шт"

    return ""


# =========================
# ЭТИКЕТКИ ДЛЯ МЕТРИК
# =========================

def _label_for_metric(key_lower: str) -> str:
    if ("выручк" in key_lower) or ("revenue" in key_lower) or ("руб" in key_lower) or ("₽" in key_lower) or ("sum" in key_lower) or ("amount" in key_lower):
        return "Выручка"
    if ("возврат" in key_lower) or ("returns" in key_lower) or ("return" in key_lower):
        return "Возвраты"
    if ("weight" in key_lower) or ("вес" in key_lower) or ("kg" in key_lower) or ("кг" in key_lower):
        return "Вес"
    if ("quantity" in key_lower) or ("qty" in key_lower) or ("колич" in key_lower) or ("шт" in key_lower):
        return "Количество"
    return key_lower


# =========================
# ПОМОЩНИКИ ДЛЯ ДАННЫХ
# =========================

def _looks_numeric(val: Any) -> bool:
    return _to_float(val) is not None


def _parse_dt(val: Any) -> Optional[_dt.date]:
    """Пытается разобрать дату (date/datetime/ISO/ YYYY-MM → 1-е число)."""
    if val is None:
        return None
    if isinstance(val, _dt.datetime):
        return val.date()
    if isinstance(val, _dt.date):
        return val
    s = str(val).strip()
    if not s:
        return None
    try:
        if re.fullmatch(r"\d{4}-\d{2}$", s):  # YYYY-MM
            s = s + "-01"
        s = s.replace("Z", "+00:00")
        return _dt.datetime.fromisoformat(s).date()
    except Exception:
        return None


def _ru_month_name(dt: _dt.date) -> str:
    months = [
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
    ]
    return months[dt.month - 1]


def _ru_month_from_name(name: str) -> str:
    m = name.strip().lower()
    mapping = {
        "january": "Январь", "february": "Февраль", "march": "Март", "april": "Апрель",
        "may": "Май", "june": "Июнь", "july": "Июль", "august": "Август",
        "september": "Сентябрь", "october": "Октябрь", "november": "Ноябрь", "december": "Декабрь",
    }
    return mapping.get(m, name)


def detect_primary_fields(row: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    """Эвристически находит поле-название и первое «главное» числовое.
    Возвращает (name_key, value_key | None).
    """
    if not row:
        return ("", None)

    keys = list(row.keys())
    name_key = keys[0]
    value_key: Optional[str] = None

    priority = ["revenue", "sum", "amount", "weight", "weight_kg", "qty", "quantity"]
    lower_map = {k.lower(): k for k in keys}

    for p in priority:
        if p in lower_map:
            value_key = lower_map[p]
            break

    if value_key is None:
        for k, v in row.items():
            if _looks_numeric(v):
                value_key = k
                break
    return (name_key, value_key)


# =========================
# HTML СБОРКА
# =========================

def _extract_title_and_period(existing_title: Optional[str]) -> Tuple[str, Optional[str]]:
    """Если existing_title уже с <b>…</b> и содержит 'Период:', разделяем.
    Иначе возвращаем <b>Отчёт</b> и None.
    """
    if not existing_title:
        return "<b>Отчёт</b>", None

    t = existing_title.strip()
    if t.startswith("<b>") and t.endswith("</b>"):
        inner = t[3:-4].strip()
        if "Период:" in inner:
            before, after = inner.split("Период:", 1)
            title = f"<b>{before.strip()}</b>"
            period_line = f"Период: {after.strip()}"
            return title, period_line
        return t, None

    return "<b>Отчёт</b>", None


def build_html_from_rows(
    rows: List[Dict[str, Any]],
    existing_title: Optional[str] = None
) -> str:
    """Собирает аккуратный HTML:
      - Первая строка — <b>Заголовок</b>
      - Опционально строка «Период: …»
      - Далее строки вида: <b>Категория</b> — Метрика: 12 345 ₽; Метрика2: 10 шт
      - Поддерживает time-series (месяцы/даты), weekN_* поля и двухуровневые группировки.
      - На выходе: СРАЗУ санитизированный HTML (под Telegram), обрезанный по лимиту.
    """
    if not rows:
        return "<b>Нет данных по заданным условиям.</b>"

    title, period_line = _extract_title_and_period(existing_title)

    # === time-series (помесячно/по датам)
    probe_keys = set(rows[0].keys())
    time_keys = [k for k in probe_keys if k in ("month_start", "month", "month_period", "date", "дата", "месяц")]
    if time_keys:
        lines_ts: List[str] = []
        for r in rows:
            # label
            dt = _parse_dt(r.get("month_start") or r.get("month_period") or r.get("date") or r.get("дата"))
            if dt:
                label = _ru_month_name(dt) if dt.day == 1 else dt.isoformat()
            elif r.get("month"):
                label = _ru_month_from_name(str(r.get("month")))
            elif r.get("месяц"):
                label = _ru_month_from_name(str(r.get("месяц")))
            else:
                label = str(r.get(time_keys[0]))

            # metrics
            parts: List[str] = []
            for k, v in r.items():
                if k in ("month_start", "month", "month_period", "date", "дата", "месяц"):
                    continue
                if _looks_numeric(v):
                    unit = unit_for_key(k.lower())
                    label_metric = _label_for_metric(k.lower())
                    parts.append(f"{label_metric}: {with_unit(v, unit)}")

            if parts:
                lines_ts.append(f"{label} — {'; '.join(parts)}")

        if lines_ts:
            # Сначала санитизируем заголовок/период и каждую строку, затем собираем.
            head = sanitize_html(title) + (("\n" + sanitize_html(period_line)) if period_line else "")
            sanitized_lines = [sanitize_html(ln) for ln in lines_ts]
            return _assemble_with_limit(head, sanitized_lines)

    # === определяем числовые и нечисловые поля
    probe = rows[0]
    non_numeric_keys: List[str] = []
    numeric_keys: List[str] = []
    for k, v in probe.items():
        (numeric_keys if _looks_numeric(v) else non_numeric_keys).append(k)

    # === один ряд, одна метрика → краткий вывод
    if (len(rows) == 1) and (len(numeric_keys) == 1):
        only_key = numeric_keys[0]
        unit = unit_for_key(only_key.lower())
        value = rows[0].get(only_key)
        parts: List[str] = [sanitize_html(title)]
        if period_line:
            parts.append(sanitize_html(period_line))
        parts.append(sanitize_html(with_unit(value, unit)))
        # Здесь нет длинных списков → просто вернуть склеенный текст
        return "\n".join(parts)

    # === weekN_* (например: week1_kg, week2_qty, week3_revenue)
    week_pattern = re.compile(r"^week(\d+)_(kg|quantity|qty|revenue)$", re.IGNORECASE)
    week_metrics: List[Tuple[int, str, str]] = []
    for k in numeric_keys:
        m = week_pattern.match(k)
        if m:
            week_metrics.append((int(m.group(1)), k, m.group(2).lower()))
    if week_metrics:
        week_metrics.sort(key=lambda t: t[0])
        unit_map = {"kg": " кг", "quantity": " шт", "qty": " шт", "revenue": " ₽"}
        name_key = non_numeric_keys[0] if non_numeric_keys else list(probe.keys())[0]
        lines: List[str] = []
        for r in rows:
            primary_name = str(r.get(name_key, "")).strip()
            if not primary_name:
                continue
            parts: List[str] = []
            for week_num, key, suffix in week_metrics:
                val = r.get(key)
                if val is None:
                    continue
                unit = unit_map.get(suffix, "")
                parts.append(f"Неделя {week_num}: {with_unit(val, unit)}")
            if parts:
                lines.append(f"<b>{primary_name}</b> — {'; '.join(parts)}")

        head = sanitize_html(title) + (("\n" + sanitize_html(period_line)) if period_line else "")
        sanitized_lines = [sanitize_html(ln) for ln in lines]
        return _assemble_with_limit(head, sanitized_lines)

    # === weekN (без суффиксов: считаем ₽ по умолчанию)
    week_simple_pattern = re.compile(r"^week(\d+)$", re.IGNORECASE)
    week_simple: List[Tuple[int, str]] = []
    for k in numeric_keys:
        m = week_simple_pattern.match(k)
        if m:
            week_simple.append((int(m.group(1)), k))
    if week_simple:
        week_simple.sort(key=lambda t: t[0])
        name_key = non_numeric_keys[0] if non_numeric_keys else list(probe.keys())[0]
        lines: List[str] = []
        for r in rows:
            primary_name = str(r.get(name_key, "")).strip()
            if not primary_name:
                continue
            parts: List[str] = []
            for week_num, key in week_simple:
                val = r.get(key)
                if val is None:
                    continue
                parts.append(f"Неделя {week_num}: {with_unit(val, ' ₽')}")
            if parts:
                lines.append(f"<b>{primary_name}</b> — {'; '.join(parts)}")

        head = sanitize_html(title) + (("\n" + sanitize_html(period_line)) if period_line else "")
        sanitized_lines = [sanitize_html(ln) for ln in lines]
        return _assemble_with_limit(head, sanitized_lines)

    # === общий случай: одна или две размерности + до 3 метрик
    name_key = non_numeric_keys[0] if non_numeric_keys else list(probe.keys())[0]
    secondary_key: Optional[str] = non_numeric_keys[1] if len(non_numeric_keys) > 1 else None

    preferred_metrics: List[str] = [k for k in numeric_keys if "total" not in k.lower()]
    metrics: List[str] = (preferred_metrics or numeric_keys)[:3]

    lines: List[str] = []

    if secondary_key and metrics:
        first_metric = metrics[0]

        # группируем по первичному ключу
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for r in rows:
            primary_name = str(r.get(name_key, "")).strip()
            groups.setdefault(primary_name, []).append(r)

        # сортируем группы по сумме первой метрики
        def _sum_metric(lst: List[Dict[str, Any]]) -> float:
            total = 0.0
            for rr in lst:
                v = _to_float(rr.get(first_metric))
                total += v or 0.0
            return total

        for primary_name, group_rows in sorted(groups.items(), key=lambda kv: _sum_metric(kv[1]), reverse=True):
            if not primary_name:
                continue
            lines.append(f"<b>{primary_name}:</b>")

            def _metric_val(rr: Dict[str, Any]) -> float:
                return _to_float(rr.get(first_metric)) or 0.0

            for rr in sorted(group_rows, key=_metric_val, reverse=True):
                sec = str(rr.get(secondary_key, "")).strip()
                if not sec:
                    continue
                unit = unit_for_key(first_metric.lower())
                lines.append(f"{sec} - {with_unit(rr.get(first_metric), unit)}")
    else:
        for r in rows:
            primary_name = str(r.get(name_key, "")).strip()
            if secondary_key:
                secondary_val = str(r.get(secondary_key, "")).strip()
                name = f"{primary_name} — {secondary_val}" if secondary_val else primary_name
            else:
                name = primary_name
            if not name:
                continue

            parts: List[str] = []
            if not metrics:
                # возьмём первый числовой
                for k, v in r.items():
                    if _looks_numeric(v):
                        parts.append(with_unit(v, unit_for_key(k.lower())))
                        break
            else:
                if len(metrics) == 1:
                    k = metrics[0]
                    if k in r and _looks_numeric(r[k]):
                        unit = unit_for_key(k.lower())
                        parts.append(with_unit(r[k], unit))
                else:
                    for k in metrics:
                        if k in r and _looks_numeric(r[k]):
                            unit = unit_for_key(k.lower())
                            label = _label_for_metric(k.lower())
                            parts.append(f"{label}: {with_unit(r[k], unit)}")

            bold_name = f"<b>{name}</b>"
            line = bold_name if not parts else f"{bold_name} — {'; '.join(parts)}"
            lines.append(line)

    head = sanitize_html(title) + (("\n" + sanitize_html(period_line)) if period_line else "")
    sanitized_lines = [sanitize_html(ln) for ln in lines]
    return _assemble_with_limit(head, sanitized_lines)


# =========================
# СБОРКА С УЧЁТОМ ЛИМИТА TELEGRAM
# =========================

def _assemble_with_limit(header_block: str, sanitized_lines: List[str]) -> str:
    """Собирает итог: header + пустая строка + список строк, при необходимости обрезает,
    не ломая HTML (строки уже санитизированы и самодостаточны).
    """
    # Лимит Telegram
    try:
        hard_limit = int(os.getenv("TELEGRAM_MAX_MESSAGE", "4000"))
    except Exception:
        hard_limit = 4000
    hard_limit = max(500, hard_limit)
    safety_tail = 200  # на футер

    header_block = sanitize_html(header_block)
    full_text = header_block + "\n\n" + "\n".join(sanitized_lines)
    if len(full_text) <= hard_limit:
        return full_text

    kept: List[str] = []
    current_len = len(header_block) + 2
    limit_for_lines = hard_limit - safety_tail

    for ln in sanitized_lines:
        add_len = len(ln) + 1
        if current_len + add_len > limit_for_lines:
            break
        kept.append(ln)
        current_len += add_len

    shown = len(kept)
    total = len(sanitized_lines)
    footer = (
        f"\n\nПоказаны первые {shown} из {total} строк. "
        f"Могу отправить полный список в Excel — напишите: в excel"
    )
    # Футер тоже санитизируем (на будущее, если появятся ссылки/теги)
    return header_block + "\n\n" + ("\n".join(kept)) + sanitize_html(footer)
