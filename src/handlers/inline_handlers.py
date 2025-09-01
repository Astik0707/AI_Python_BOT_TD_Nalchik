from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from src.handlers.cards import get_card_by_filename, resolve_card_path
from src.utils.logger import get_logger
import os

logger = get_logger(__name__)


async def handle_card_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает нажатия на inline кнопки карточек
    """
    query = update.callback_query
    await query.answer()
    
    if not query.data:
        return
    
    chat_id = query.message.chat_id
    data = query.data
    
    logger.info(f"🎯 Inline callback: {data} для chat_id: {chat_id}")
    
    try:
        if data == "cards_error":
            await query.edit_message_text("❌ Карточки торговых представителей временно недоступны")
            return
            
        elif data == "card_all":
            # Отправляем все карточки
            await handle_all_cards(context, chat_id, query)
            return
            
        elif data.startswith("card_"):
            # Отправляем конкретную карточку
            card_index = data[5:]  # Убираем "card_" из начала
            await handle_single_card(context, chat_id, card_index, query)
            return
            
        else:
            await query.edit_message_text("❌ Неизвестная команда")
            
    except Exception as e:
        logger.error(f"❌ Ошибка обработки inline callback: {e}")
        await query.edit_message_text("❌ Произошла ошибка при обработке запроса")


async def handle_single_card(context: ContextTypes.DEFAULT_TYPE, chat_id: int, card_index: str, query):
    """
    Обрабатывает отправку одной карточки по индексу
    """
    try:
        from src.handlers.cards import get_available_cards
        
        # Получаем список всех карточек
        available_cards = get_available_cards()
        
        if not available_cards:
            await query.edit_message_text("❌ Карточки не найдены")
            return
        
        # Преобразуем индекс в число
        try:
            index = int(card_index)
        except ValueError:
            await query.edit_message_text("❌ Неверный индекс карточки")
            return
        
        # Проверяем, что индекс в допустимых пределах
        if index < 0 or index >= len(available_cards):
            await query.edit_message_text("❌ Индекс карточки вне диапазона")
            return
        
        # Получаем информацию о карточке по индексу
        card_info = available_cards[index]
        
        # Отправляем карточку
        filepath = card_info["filepath"]
        
        if not os.path.exists(filepath):
            await query.edit_message_text("❌ Файл карточки не найден")
            return
        
        # Отправляем HTML файл
        with open(filepath, 'rb') as file:
            await context.bot.send_document(
                chat_id=chat_id,
                document=file,
                filename=card_info["filename"],
                caption=f"📋 Карточка: {card_info['full_name']}"
            )
        
        # Удаляем inline меню
        await query.edit_message_text(f"✅ Карточка {card_info['full_name']} отправлена")
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки карточки по индексу {card_index}: {e}")
        await query.edit_message_text("❌ Ошибка при отправке карточки")


async def handle_all_cards(context: ContextTypes.DEFAULT_TYPE, chat_id: int, query):
    """
    Обрабатывает отправку всех карточек
    """
    try:
        from src.handlers.cards import get_available_cards
        
        available_cards = get_available_cards()
        
        if not available_cards:
            await query.edit_message_text("❌ Карточки не найдены")
            return
        
        # Отправляем сообщение о начале отправки
        await query.edit_message_text(f"📁 Отправляю {len(available_cards)} карточек...")
        
        # Отправляем каждую карточку
        for card in available_cards:
            try:
                filepath = card["filepath"]
                
                if os.path.exists(filepath):
                    with open(filepath, 'rb') as file:
                        await context.bot.send_document(
                            chat_id=chat_id,
                            document=file,
                            filename=card["filename"],
                            caption=f"📋 {card['full_name']}"
                        )
                        
            except Exception as e:
                logger.error(f"❌ Ошибка отправки карточки {card['filename']}: {e}")
                continue
        
        # Обновляем сообщение
        await context.bot.edit_message_text(
            f"✅ Отправлено {len(available_cards)} карточек",
            chat_id=chat_id,
            message_id=query.message.message_id
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки всех карточек: {e}")
        await query.edit_message_text("❌ Ошибка при отправке карточек")


async def show_cards_menu(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """
    Показывает меню с карточками
    """
    try:
        from src.handlers.cards import create_cards_menu
        
        menu = create_cards_menu()
        
        await context.bot.send_message(
            chat_id=chat_id,
            text="📋 Выберите карточку торгового представителя:",
            reply_markup=menu
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка показа меню карточек: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ Ошибка при создании меню карточек"
        )
