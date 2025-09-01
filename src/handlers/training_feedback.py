"""
Обработчик обратной связи для обучения AI агента
"""
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from src.utils.logger import get_logger
from src.db.pool import get_pool
import asyncio

logger = get_logger(__name__)

# Состояния пользователей для сбора комментариев
user_states = {}

async def handle_training_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает нажатие кнопки 'Отправить на обучение'"""
    logger.info(f"🎯 handle_training_feedback вызван для update: {update}")
    
    query = update.callback_query
    chat_id = query.from_user.id
    
    logger.info(f"🎯 Получен callback: {query.data} для chat_id: {chat_id}")
    
    if not query.data.startswith("training_"):
        logger.info(f"❌ Callback не начинается с 'training_': {query.data}")
        return
    
    try:
        # Извлекаем данные из callback
        logger.info(f"🔍 Разбираем callback_data: {query.data}")
        parts = query.data.split("_")
        logger.info(f"🔍 Части callback_data: {parts}")
        
        if len(parts) >= 2:  # training_624 -> 2 части
            log_id = int(parts[1])  # Берем вторую часть (индекс 1)
            logger.info(f"🔍 Извлечен log_id: {log_id}")
            
            # Сохраняем состояние пользователя
            user_states[chat_id] = {
                "log_id": log_id,
                "waiting_for_comment": True
            }
            logger.info(f"🔍 Установлено состояние пользователя: {user_states[chat_id]}")
            
            # Показываем красивую форму для комментария
            logger.info(f"🔍 Вызываем show_comment_form для log_id: {log_id}")
            await show_comment_form(query, context, log_id)
            logger.info(f"✅ show_comment_form выполнен успешно")
            
    except Exception as e:
        logger.error(f"❌ Ошибка обработки training feedback: {e}")
        await query.answer("❌ Произошла ошибка")

async def show_comment_form(query, context, log_id):
    """Показывает красивую форму для ввода комментария"""
    
    # Создаем inline клавиатуру с вариантами
    keyboard = [
        [
            InlineKeyboardButton("📝 Оставить комментарий", callback_data=f"comment_form_{log_id}"),
            InlineKeyboardButton("❌ Отмена", callback_data="comment_cancel")
        ]
    ]
    
    markup = InlineKeyboardMarkup(keyboard)
    
    # Красивое сообщение с эмодзи
    message_text = (
        "🎯 **Обратная связь для обучения AI агента**\n\n"
        "💡 **Помогите улучшить качество ответов!**\n\n"
        "**Что можно указать:**\n"
        "• 🔍 Точность и полнота ответа\n"
        "• 📊 Качество данных и графиков\n"
        "• 🎨 Удобство представления информации\n"
        "• ⚡ Скорость работы\n"
        "• 🚫 Найденные ошибки или неточности\n"
        "• 💭 Предложения по улучшению\n\n"
        "**Нажмите кнопку ниже, чтобы оставить комментарий:**"
    )
    
    await query.edit_message_text(
        text=message_text,
        reply_markup=markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_comment_form(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает форму комментария"""
    query = update.callback_query
    chat_id = query.from_user.id
    
    if query.data == "comment_cancel":
        await query.edit_message_text("❌ Комментарий отменен")
        if chat_id in user_states:
            del user_states[chat_id]
        return
    
    if query.data.startswith("comment_form_"):
        log_id = int(query.data.split("_")[2])  # comment_form_624 -> 3 части, берем третью
        
        # Показываем инструкцию для ввода комментария
        await show_comment_instructions(query, context, log_id)

async def show_comment_instructions(query, context, log_id):
    """Показывает инструкции для ввода комментария"""
    
    # Обновляем состояние пользователя
    if query.from_user.id in user_states:
        user_states[query.from_user.id]["log_id"] = log_id
        user_states[query.from_user.id]["waiting_for_comment"] = True
    
    message_text = (
        "✍️ **Введите ваш комментарий**\n\n"
        "**Формат комментария:**\n"
        "• Опишите проблему или предложение\n"
        "• Укажите конкретные детали\n"
        "• Будьте конструктивны\n\n"
        "**Примеры:**\n"
        "• \"Ответ неполный, не хватает данных по регионам\"\n"
        "• \"График нечитаемый, нужны подписи осей\"\n"
        "• \"Отлично! Все данные корректны\"\n\n"
        "**Просто напишите ваш комментарий в чат:**"
    )
    
    # Кнопка отмены
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="comment_cancel")]]
    markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=message_text,
        reply_markup=markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_comment_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает введенный пользователем комментарий"""
    chat_id = update.effective_chat.id
    comment_text = update.message.text
    
    if chat_id not in user_states or not user_states[chat_id].get("waiting_for_comment"):
        return
    
    try:
        log_id = user_states[chat_id]["log_id"]
        
        # Сохраняем комментарий в БД
        await save_comment_to_db(log_id, chat_id, comment_text)
        
        # Показываем подтверждение
        await show_comment_confirmation(context, chat_id, comment_text)
        
        # Очищаем состояние пользователя
        del user_states[chat_id]
        
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения комментария: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ Произошла ошибка при сохранении комментария"
        )

async def save_comment_to_db(log_id: int, chat_id: int, comment: str) -> None:
    """Сохраняет комментарий в базу данных"""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Обновляем существующую запись или создаем новую
            await conn.execute('''
                UPDATE training_clicks 
                SET comment = $1, status = 'в очереди', clicked_at = NOW()
                WHERE log_id = $2 AND clicked_by = $3
            ''', comment, log_id, chat_id)
            
            # Если запись не найдена, создаем новую
            if await conn.fetchval('SELECT COUNT(*) FROM training_clicks WHERE log_id = $1 AND clicked_by = $2', log_id, chat_id) == 0:
                await conn.execute('''
                    INSERT INTO training_clicks (log_id, clicked_by, chat_id, status, comment, clicked_at)
                    VALUES ($1, $2, $3, 'в очереди', $4, NOW())
                ''', log_id, chat_id, chat_id, comment)
            
            logger.info(f"✅ Комментарий сохранен для log_id: {log_id}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения комментария в БД: {e}")
        raise

async def show_comment_confirmation(context: ContextTypes.DEFAULT_TYPE, chat_id: int, comment: str) -> None:
    """Показывает подтверждение сохранения комментария"""
    
    # Обрезаем длинный комментарий для отображения
    display_comment = comment[:100] + "..." if len(comment) > 100 else comment
    
    message_text = (
        "✅ **Комментарий успешно сохранен!**\n\n"
        "📝 **Ваш комментарий:**\n"
        f"_{display_comment}_\n\n"
        "🎯 **Спасибо за обратную связь!**\n\n"
        "💡 Ваш комментарий поможет улучшить качество ответов AI агента.\n"
        "Мы анализируем все отзывы и постоянно работаем над улучшениями.\n\n"
        "🚀 **Продолжайте использовать бота!**"
    )
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=message_text,
        parse_mode=ParseMode.MARKDOWN
    )

def is_waiting_for_comment(chat_id: int) -> bool:
    """Проверяет, ждет ли пользователь ввода комментария"""
    return chat_id in user_states and user_states[chat_id].get("waiting_for_comment", False)

def get_user_state(chat_id: int):
    """Получает состояние пользователя"""
    return user_states.get(chat_id)
