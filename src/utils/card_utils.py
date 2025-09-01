import os
import re
from typing import List, Dict, Optional, Tuple
from difflib import SequenceMatcher

def get_available_cards() -> List[Dict[str, str]]:
    """
    Получает список всех доступных карточек торговых представителей
    """
    cards_dir = os.environ.get("CARDS_DIR", "/home/adminvm/cards")
    cards = []
    
    if not os.path.exists(cards_dir):
        return cards
    
    for filename in os.listdir(cards_dir):
        if filename.startswith("card_") and filename.endswith(".html"):
            # Извлекаем имя из filename: card_Хежев_Залим_Исмагилович.html
            name_part = filename[5:-5]  # Убираем "card_" и ".html"
            # Заменяем подчеркивания на пробелы для читаемости
            readable_name = name_part.replace("_", " ")
            
            cards.append({
                "filename": filename,
                "full_name": readable_name,
                "filepath": os.path.join(cards_dir, filename)
            })
    
    return cards

def find_best_card_match(search_text: str, available_cards: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    """
    Находит лучшее совпадение для поискового текста среди доступных карточек
    """
    if not search_text or not available_cards:
        return None
    
    search_text = search_text.lower().strip()
    best_match = None
    best_score = 0
    
    for card in available_cards:
        full_name = card["full_name"].lower()
        
        # Прямое включение (например, "хежев" в "Хежев Залим Исмагилович")
        if search_text in full_name:
            return card
        
        # Поиск по частям имени
        name_parts = full_name.split()
        for part in name_parts:
            if search_text in part or part in search_text:
                score = len(part) / len(search_text)  # Чем длиннее совпадение, тем лучше
                if score > best_score:
                    best_score = score
                    best_match = card
        
        # Fuzzy matching для похожих имен
        similarity = SequenceMatcher(None, search_text, full_name).ratio()
        if similarity > 0.6 and similarity > best_score:  # Порог схожести 60%
            best_score = similarity
            best_match = card
    
    return best_match

def normalize_card_name(name: str) -> str:
    """
    Нормализует имя для поиска файла карточки
    """
    if not name:
        return ""
    
    # Убираем лишние пробелы и приводим к нижнему регистру
    normalized = re.sub(r'\s+', ' ', name.strip()).lower()
    
    # Заменяем пробелы на подчеркивания для создания имени файла
    filename_part = normalized.replace(" ", "_")
    
    return filename_part

def get_card_info(card_name: str) -> Optional[Dict[str, str]]:
    """
    Получает информацию о карточке по имени
    """
    available_cards = get_available_cards()
    best_match = find_best_card_match(card_name, available_cards)
    
    if best_match:
        return {
            "found": True,
            "filename": best_match["filename"],
            "full_name": best_match["full_name"],
            "filepath": best_match["filepath"],
            "search_query": card_name
        }
    else:
        return {
            "found": False,
            "search_query": card_name,
            "available_cards": [card["full_name"] for card in available_cards[:10]]  # Первые 10 для подсказки
        }
