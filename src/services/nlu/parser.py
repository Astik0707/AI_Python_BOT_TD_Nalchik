from __future__ import annotations
from typing import Any, Dict, Optional, Tuple
import re
import datetime


RU_MONTHS = {
    "январ": 1, "феврал": 2, "март": 3, "апрел": 4, "мая": 5, "июн": 6,
    "июл": 7, "август": 8, "сентябр": 9, "октябр": 10, "ноябр": 11, "декабр": 12,
}


def _norm(s: str) -> str:
    return (s or "").lower().replace("ё", "е")


def _pick_metric(t: str) -> str:
    if any(k in t for k in ["выручк", "продаж", "доход", "оборот"]):
        return "revenue"
    if any(k in t for k in ["вес", "кг", "тонн"]):
        return "weight_kg"
    if any(k in t for k in ["шт", "штук", "количеств"]):
        return "quantity"
    return "revenue"


def _pick_dimension(t: str) -> Optional[str]:
    if re.search(r"по\s+торгов|по\s+менедж", t):
        return "manager"
    if re.search(r"по\s+бренд", t):
        return "brand"
    if re.search(r"по\s+клиент", t):
        return "client"
    if re.search(r"по\s+регион", t):
        return "region"
    if re.search(r"по\s+канал", t):
        return "channel"
    if re.search(r"по\s+(товар|продукт)", t):
        return "product"
    return None


def _pick_granularity(t: str) -> Optional[str]:
    if "по месяц" in t:
        return "month"
    if "по недел" in t:
        return "week"
    if "по дням" in t or "по дн" in t:
        return "day"
    if "динамик" in t or "тренд" in t:
        # default trend granularity
        return "month"
    return None


def _parse_period(t: str, current_date: Optional[datetime.date]) -> Tuple[Optional[datetime.date], Optional[datetime.date]]:
    if current_date is None:
        current_date = datetime.date.today()

    # Год: "за 2025"
    m = re.search(r"за\s+(20\d{2})", t)
    if m:
        y = int(m.group(1))
        return datetime.date(y, 1, 1), datetime.date(y + 1, 1, 1)

    # Месяц: "за март" или "за март 2025"
    for stem, mm in RU_MONTHS.items():
        m = re.search(rf"за\s+{stem}[а-я]*\s*(20\d{{2}})?", t)
        if m:
            y = int(m.group(1)) if m.group(1) else current_date.year
            start = datetime.date(y, mm, 1)
            end = (start.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
            return start, end

    # Квартал: "за квартал" (текущий) или "за 2 квартал 2025"
    m = re.search(r"за\s*(\d)\s*квартал\s*(20\d{2})?", t)
    if m:
        q = int(m.group(1))
        y = int(m.group(2)) if m.group(2) else current_date.year
        mm = (q - 1) * 3 + 1
        start = datetime.date(y, mm, 1)
        end = datetime.date(y, mm + 3, 1) if mm <= 9 else datetime.date(y + 1, (mm + 3) % 12, 1)
        return start, end

    if "за квартал" in t:
        # текущий квартал
        q = (current_date.month - 1) // 3 + 1
        mm = (q - 1) * 3 + 1
        start = datetime.date(current_date.year, mm, 1)
        end = datetime.date(current_date.year, mm + 3, 1) if mm <= 9 else datetime.date(current_date.year + 1, (mm + 3) % 12, 1)
        return start, end

    return None, None


def parse_intent(text: str, current_date: Optional[datetime.date]) -> Dict[str, Any]:
    t = _norm(text)
    metric = _pick_metric(t)
    dimension = _pick_dimension(t)
    gran = _pick_granularity(t)
    start, end = _parse_period(t, current_date)
    return {
        "metric": metric,
        "dimension": dimension,
        "time_granularity": gran,
        "period": {
            "start": start.isoformat() if start else None,
            "end": end.isoformat() if end else None,
        },
    }


