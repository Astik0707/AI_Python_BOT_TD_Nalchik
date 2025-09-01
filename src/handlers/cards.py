from __future__ import annotations
import os
from typing import Optional, List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from src.utils.card_utils import get_available_cards, normalize_card_name


def create_cards_menu() -> InlineKeyboardMarkup:
    """
    Создает inline меню со всеми доступными карточками
    """
    available_cards = get_available_cards()
    
    if not available_cards:
        # Если карточек нет, показываем сообщение об ошибке
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Карточки недоступны", callback_data="cards_error")
        ]])
    
    # Группируем карточки по 2 в ряд для компактности
    buttons = []
    row = []
    
    for i, card in enumerate(available_cards):
        # Создаем безопасный callback_data с индексом
        safe_callback = f"card_{i:03d}"  # card_000, card_001, etc.
        button = InlineKeyboardButton(
            card["full_name"], 
            callback_data=safe_callback
        )
        row.append(button)
        
        # Если в ряду 2 кнопки, добавляем ряд и начинаем новый
        if len(row) == 2:
            buttons.append(row)
            row = []
    
    # Добавляем последний неполный ряд, если есть
    if row:
        buttons.append(row)
    
    # Добавляем кнопку "Все карточки" внизу
    buttons.append([
        InlineKeyboardButton("📁 Все карточки (архив)", callback_data="card_all")
    ])
    
    return InlineKeyboardMarkup(buttons)


def resolve_card_path(rep_name: str) -> Optional[str]:
    """
    Разрешает путь к карточке торгового представителя.
    Использует улучшенный поиск с fuzzy matching.
    """
    if not rep_name:
        return None

    # 'all' обрабатывается на уровне вызова (отправка архива/нескольких файлов)
    if rep_name.strip().lower() == "all":
        return None

    # Используем новую систему поиска карточек
    card_info = get_card_info(rep_name)
    
    if card_info and card_info.get("found"):
        return card_info["filepath"]
    
    # Fallback на старую логику для совместимости
    cards_dir = os.environ.get("CARDS_DIR", "/home/adminvm/cards")
    normalized = normalize_card_name(rep_name)
    filename = f"card_{normalized}.html"
    filepath = os.path.join(cards_dir, filename)

    if os.path.exists(filepath):
        return filepath
    
    return None


def get_card_by_filename(filename: str) -> Optional[dict]:
    """
    Получает информацию о карточке по имени файла
    """
    available_cards = get_available_cards()
    
    for card in available_cards:
        if card["filename"] == filename:
            return card
    
    return None
