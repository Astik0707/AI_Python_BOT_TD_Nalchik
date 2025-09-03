from __future__ import annotations
from typing import Any, Dict, List, Optional
import datetime
import os
from decimal import Decimal
import re


def format_number_ru(value: Any) -> str:
    """Format number with space thousands and comma decimal according to ТЗ.
    Accepts int/float/Decimal/str that looks like number.
    """
    try:
        if isinstance(value, Decimal):
            num = float(value)
        elif isinstance(value, (int, float)):
            num = float(value)
        else:
            num = float(str(value).replace(" ", "").replace(",", "."))
        whole, frac = f"{num:.2f}".split(".")
        groups: List[str] = []
        for i in range(len(whole), 0, -3):
            start = max(i - 3, 0)
            groups.append(whole[start:i])
        whole_spaced = " ".join(reversed(groups))
        return f"{whole_spaced},{frac}"
    except Exception:
        return str(value)


def with_unit(value: Any, unit: str) -> str:
    formatted = format_number_ru(value)
    return f"{formatted}{unit}" if unit else formatted


def detect_primary_fields(row: Dict[str, Any]) -> tuple[str, Optional[str]]:
    """Heuristically detect display name field and primary numeric field.
    Returns (name_key, value_key or None).
    """
    if not row:
        return ("", None)
    keys = list(row.keys())
    name_key = keys[0]
    value_key: Optional[str] = None
    # Try to choose obvious numeric columns
    priority = [
        "revenue", "sum", "amount", "weight", "weight_kg", "qty", "quantity",
    ]
    lower_map = {k.lower(): k for k in keys}
    for p in priority:
        if p in lower_map:
            value_key = lower_map[p]
            break
    if value_key is None:
        for k, v in row.items():
            if isinstance(v, (int, float, Decimal)):
                value_key = k
                break
    return (name_key, value_key)


def unit_for_key(value_key_lower: Optional[str]) -> str:
    if not value_key_lower:
        return ""
    # Currency
    if ("revenue" in value_key_lower) or ("sum" in value_key_lower) or ("amount" in value_key_lower) or ("return" in value_key_lower):
        return " ₽"
    if ("выручк" in value_key_lower) or ("руб" in value_key_lower) or ("₽" in value_key_lower):
        return " ₽"
    # Weight
    if ("weight" in value_key_lower) or ("kg" in value_key_lower):
        return " кг"
    if ("вес" in value_key_lower) or ("кг" in value_key_lower):
        return " кг"
    # Quantity
    if ("quantity" in value_key_lower) or ("qty" in value_key_lower):
        return " шт"
    if ("шт" in value_key_lower):
        return " шт"
    return ""


def build_html_from_rows(rows: List[Dict[str, Any]], existing_title: Optional[str] = None) -> str:
    """Build strict HTML per §6: title in <b>..</b>, list lines with units.
    Supports multiple numeric metrics per row and labels them.
    """
    if not rows:
        return "<b>Нет данных по заданным условиям.</b>"

    # Prepare title and optional period line
    period_line: Optional[str] = None
    if existing_title and existing_title.strip().startswith("<b>") and existing_title.strip().endswith("</b>"):
        # Extract inner text to separate accidental embedded period
        inner = existing_title.strip()[3:-4].strip()
        if "Период:" in inner:
            before, after = inner.split("Период:", 1)
            title = f"<b>{before.strip()}</b>"
            period_line = f"Период: {after.strip()}"
        else:
            title = existing_title.strip()
    else:
        title = "<b>Отчёт</b>"

    def _looks_numeric(val: Any) -> bool:
        if isinstance(val, (int, float, Decimal)):
            return True
        try:
            s = str(val).strip().replace("\u00A0", " ")
            s = s.replace(" ", "").replace(",", ".")
            float(s)
            return True
        except Exception:
            return False

    # Special case: time series by month/day with multiple metrics
    def _parse_dt(val: Any) -> Optional[datetime.date]:
        try:
            if isinstance(val, datetime.datetime):
                return val.date()
            if isinstance(val, datetime.date):
                return val
            s = str(val).strip()
            # Handle YYYY-MM by assuming day = 01
            if len(s) == 7 and s[4] == '-' and s[:4].isdigit() and s[5:7].isdigit():
                s = s + "-01"
            # Try ISO
            return datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).date()
        except Exception:
            return None

    def _ru_month_name(dt: datetime.date) -> str:
        months = [
            "Январь","Февраль","Март","Апрель","Май","Июнь",
            "Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"
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

    probe_keys = set(rows[0].keys())
    # Heuristic: treat as time-series if there is any date-like or month-like key
    time_keys = [k for k in probe_keys if k in ("month_start", "month", "month_period", "date", "дата", "месяц")]
    if time_keys:
        # Build label per row
        lines_ts: List[str] = []
        for r in rows:
            label: Optional[str] = None
            # Prefer explicit date fields
            dt = _parse_dt(r.get("month_start") or r.get("month_period") or r.get("date") or r.get("дата"))
            if dt:
                label = _ru_month_name(dt) if (isinstance(dt, datetime.date) and dt.day == 1) else dt.isoformat()
            elif r.get("month"):
                label = _ru_month_from_name(str(r.get("month")))
            elif r.get("месяц"):
                label = _ru_month_from_name(str(r.get("месяц")))
            else:
                label = str(r.get(time_keys[0]))

            # Collect metrics present in this row
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
            header_block = title + ("\n" + period_line if period_line else "")
            return header_block + "\n\n" + "\n".join(lines_ts)

    # Determine dimension and numeric metrics
    probe = rows[0]
    non_numeric_keys: List[str] = []
    numeric_keys: List[str] = []
    for k, v in probe.items():
        if _looks_numeric(v):
            numeric_keys.append(k)
        else:
            non_numeric_keys.append(k)

    # Special case: single row with single numeric metric -> return compact summary (optionally with period)
    if (len(rows) == 1) and (len(numeric_keys) == 1):
        only_key = numeric_keys[0]
        unit = unit_for_key(only_key.lower())
        value = rows[0].get(only_key)
        formatted = with_unit(value, unit)
        period_line = None
        if "period" in probe and isinstance(probe.get("period"), str) and probe.get("period").strip():
            period_line = f"Период: {probe.get('period').strip()}"
        parts: List[str] = []
        if title:
            parts.append(title)
        else:
            parts.append("<b>Отчёт</b>")
        if period_line:
            parts.append(period_line)
        parts.append(formatted)
        return "\n".join(parts)

    name_key = non_numeric_keys[0] if non_numeric_keys else list(probe.keys())[0]
    secondary_key: Optional[str] = non_numeric_keys[1] if len(non_numeric_keys) > 1 else None

    # Prefer per-dimension metric if present (e.g., category_revenue vs total_revenue)
    preferred_metrics: List[str] = []
    for k in numeric_keys:
        lk = k.lower()
        if "total" in lk:
            continue
        preferred_metrics.append(k)
    metrics: List[str] = (preferred_metrics or numeric_keys)[:3]  # display up to 3 metrics

    # Special case: weekly trend columns like week1_kg, week2_qty, week3_revenue
    week_pattern = re.compile(r"^week(\d+)_(kg|quantity|qty|revenue)$", re.IGNORECASE)
    week_metrics: List[tuple[int, str, str]] = []  # (week_number, key, suffix)
    for k in numeric_keys:
        m = week_pattern.match(k)
        if m:
            week_metrics.append((int(m.group(1)), k, m.group(2).lower()))
    if week_metrics:
        week_metrics.sort(key=lambda t: t[0])
        unit_map = {"kg": " кг", "quantity": " шт", "qty": " шт", "revenue": " ₽"}
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
        header_block = title + ("\n" + period_line if period_line else "")
        return header_block + "\n\n" + "\n".join(lines)

    # Special case: weekly trend columns like week1, week2, week3 (assume revenue by default)
    week_simple_pattern = re.compile(r"^week(\d+)$", re.IGNORECASE)
    week_simple: List[tuple[int, str]] = []
    for k in numeric_keys:
        m = week_simple_pattern.match(k)
        if m:
            week_simple.append((int(m.group(1)), k))
    if week_simple:
        week_simple.sort(key=lambda t: t[0])
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
        header_block = title + ("\n" + period_line if period_line else "")
        return header_block + "\n\n" + "\n".join(lines)

    lines: List[str] = []
    # If two dimensions present, render grouped: "Primary:\nSecondary - metric"
    if secondary_key and metrics:
        first_metric = metrics[0]
        # Group rows by primary dimension
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for r in rows:
            primary_name = str(r.get(name_key, "")).strip()
            groups.setdefault(primary_name, []).append(r)
        # Order groups by sum of first metric desc
        def _sum_metric(lst: List[Dict[str, Any]]) -> float:
            total = 0.0
            for rr in lst:
                v = rr.get(first_metric)
                try:
                    if isinstance(v, (int, float, Decimal)):
                        total += float(v)
                    else:
                        s = str(v).strip().replace(" ", "").replace(",", ".")
                        total += float(s)
                except Exception:
                    continue
            return total
        for primary_name, group_rows in sorted(groups.items(), key=lambda kv: _sum_metric(kv[1]), reverse=True):
            if not primary_name:
                continue
            lines.append(f"<b>{primary_name}:</b>")
            # Order inner by metric desc
            def _metric_val(rr: Dict[str, Any]) -> float:
                v = rr.get(first_metric)
                try:
                    return float(v) if isinstance(v, (int, float, Decimal)) else float(str(v).replace(" ", "").replace(",", "."))
                except Exception:
                    return 0.0
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
                for k, v in r.items():
                    if _looks_numeric(v):
                        parts.append(with_unit(v, unit_for_key(k.lower())))
                        break
            else:
                if len(metrics) == 1:
                    k = metrics[0]
                    if k in r and isinstance(r[k], (int, float, Decimal)):
                        unit = unit_for_key(k.lower())
                        parts.append(with_unit(r[k], unit))
                else:
                    for k in metrics:
                        if k in r and isinstance(r[k], (int, float, Decimal)):
                            unit = unit_for_key(k.lower())
                            lk = k.lower()
                            if ("выручк" in lk) or ("revenue" in lk) or ("руб" in lk) or ("₽" in lk) or ("sum" in lk) or ("amount" in lk):
                                label = "Выручка"
                            elif ("возврат" in lk) or ("returns" in lk) or ("return" in lk):
                                label = "Возвраты"
                            elif ("weight" in lk) or ("вес" in lk) or ("kg" in lk) or ("кг" in lk):
                                label = "Вес"
                            elif ("quantity" in lk) or ("qty" in lk) or ("колич" in lk) or ("шт" in lk):
                                label = "Количество"
                            else:
                                label = k.replace("₽", "").strip()
                            parts.append(f"{label}: {with_unit(r[k], unit)}")
            bold_name = f"<b>{name}</b>"
            line = bold_name if not parts else f"{bold_name} — {'; '.join(parts)}"
            lines.append(line)

    header_block = title + ("\n" + period_line if period_line else "")

    # Respect Telegram ~4096 chars limit. Leave room for footer.
    try:
        max_len_env = int(os.getenv("TELEGRAM_MAX_MESSAGE", "4000"))
    except Exception:
        max_len_env = 4000
    safety_tail = 200  # reserve for footer if truncated
    hard_limit = max(500, max_len_env)

    full_body = "\n".join(lines) if lines else ""
    full_text = header_block + "\n\n" + full_body
    if len(full_text) <= hard_limit:
        return full_text

    # Trim lines to fit into the limit and add footer
    kept: List[str] = []
    current_len = len(header_block) + 2
    limit_for_lines = hard_limit - safety_tail
    for ln in lines:
        next_len = current_len + len(ln) + 1
        if next_len > limit_for_lines:
            break
        kept.append(ln)
        current_len = next_len

    shown = len(kept)
    total = len(lines)
    footer = f"\n\nПоказаны первые {shown} из {total} строк. Могу отправить полный список в Excel — напишите: в excel"
    return header_block + "\n\n" + ("\n".join(kept)) + footer



