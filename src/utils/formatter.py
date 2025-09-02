from __future__ import annotations
from typing import Any, Dict, List, Optional
import os
from decimal import Decimal


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

    # Determine dimension and numeric metrics
    probe = rows[0]
    non_numeric_keys: List[str] = []
    numeric_keys: List[str] = []
    for k, v in probe.items():
        if isinstance(v, (int, float, Decimal)):
            numeric_keys.append(k)
        else:
            non_numeric_keys.append(k)

    name_key = non_numeric_keys[0] if non_numeric_keys else list(probe.keys())[0]
    metrics: List[str] = numeric_keys[:3]  # display up to 3 metrics

    lines: List[str] = []
    for r in rows:
        name = str(r.get(name_key, "")).strip()
        if not name:
            continue
        parts: List[str] = []
        if not metrics:
            # fallback single numeric search
            for k, v in r.items():
                if isinstance(v, (int, float, Decimal)):
                    parts.append(with_unit(v, unit_for_key(k.lower())))
                    break
        else:
            if len(metrics) == 1:
                # One metric: do not show label, only value + unit as per UX
                k = metrics[0]
                if k in r and isinstance(r[k], (int, float, Decimal)):
                    unit = unit_for_key(k.lower())
                    parts.append(with_unit(r[k], unit))
            else:
                for k in metrics:
                    if k in r and isinstance(r[k], (int, float, Decimal)):
                        unit = unit_for_key(k.lower())
                        # Use short localized label
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



