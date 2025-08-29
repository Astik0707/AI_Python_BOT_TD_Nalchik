from __future__ import annotations
import os
from typing import Optional


def resolve_card_path(rep_name: str) -> Optional[str]:
    """
    Разрешает путь к карточке торгового представителя.
    Поддерживает имя в стиле n8n: пробелы -> '_' и вариант 'all'.
    """
    if not rep_name:
        return None

    # 'all' обрабатывается на уровне вызова (отправка архива/нескольких файлов)
    if rep_name.strip().lower() == "all":
        return None

    cards_dir = os.environ.get("CARDS_DIR", "/home/adminvm/cards")

    # Нормализация имени, как в n8n Code4: пробелы заменяем на '_'
    normalized = rep_name.replace(" ", "_")
    filename = f"card_{normalized}.html"
    filepath = os.path.join(cards_dir, filename)

    if os.path.exists(filepath):
        return filepath
    return None
