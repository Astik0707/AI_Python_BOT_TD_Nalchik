from __future__ import annotations
from typing import Any, Dict, List, Optional
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
    if ("revenue" in value_key_lower) or ("sum" in value_key_lower) or ("amount" in value_key_lower):
        return " ₽"
    if ("weight" in value_key_lower) or ("kg" in value_key_lower):
        return " кг"
    if ("quantity" in value_key_lower) or ("qty" in value_key_lower):
        return " шт"
    return ""


def build_html_from_rows(rows: List[Dict[str, Any]], existing_title: Optional[str] = None) -> str:
    """Build strict HTML per §6: title in <b>..</b>, list lines with units.
    Uses heuristic to pick name/value columns and infer units.
    """
    if not rows:
        return "<b>Нет данных по заданным условиям.</b>"

    title = existing_title if (existing_title and existing_title.strip().startswith("<b>") and existing_title.strip().endswith("</b>")) else "<b>Результаты запроса</b>"

    name_key, value_key = detect_primary_fields(rows[0])
    unit = unit_for_key(value_key.lower() if value_key else None)

    lines: List[str] = []
    for r in rows[:20]:
        name = str(r.get(name_key, "")).strip()
        if not name:
            continue
        if value_key and value_key in r and isinstance(r[value_key], (int, float, Decimal)):
            line = f"{name} — {with_unit(r[value_key], unit)}"
        else:
            # Fallback: search first numeric field
            numeric_val: Optional[Any] = None
            for k, v in r.items():
                if isinstance(v, (int, float, Decimal)):
                    numeric_val = v
                    unit = unit_for_key(k.lower()) or unit
                    break
            if numeric_val is None:
                line = name
            else:
                line = f"{name} — {with_unit(numeric_val, unit)}"
        lines.append(line)

    return title + "\n\n" + ("\n".join(lines) if lines else "")


