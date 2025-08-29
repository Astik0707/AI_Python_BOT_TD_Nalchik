from __future__ import annotations
import os
from typing import Optional
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.db.auth import check_authorized_chat
from src.ai.agent import run_ai_for_text
from src.utils.html_sanitize import sanitize_html
from src.db.logs import log_interaction
from src.utils.logger import get_logger
from src.utils.memory import append_message, clear_history
from src.utils.debug import tg_debug, is_debug
from typing import List, Dict
import re

logger = get_logger("handlers.text")

# Константы для валидации
MAX_TEXT_LENGTH = 4096
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


def validate_text(text: str) -> bool:
    """Валидация текстового сообщения"""
    if not text or not text.strip():
        return False
    if len(text) > MAX_TEXT_LENGTH:
        return False
    return True


async def process_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик текстовых сообщений"""
    chat_id = update.effective_chat.id
    user = update.effective_user
    text = update.effective_message.text or ''

    try:
        await tg_debug(context, chat_id, f"<code>recv:</code> {sanitize_html(text)}")

        # Сброс контекста по ключевой фразе
        if "новый запрос" in text.lower():
            await clear_history(chat_id)
            await tg_debug(context, chat_id, "🔁 Контекст очищен по запросу пользователя")

        # Валидация входных данных
        if not validate_text(text):
            await context.bot.send_message(
                chat_id=chat_id, 
                text="❌ Сообщение слишком длинное или пустое"
            )
            return

        # 1) Проверка авторизации
        if not await check_authorized_chat(chat_id):
            await context.bot.send_message(
                chat_id=chat_id, 
                text="❌ У вас нет доступа к этому боту"
            )
            await tg_debug(context, chat_id, "⛔ Неавторизованный чат")
            return

        await tg_debug(context, chat_id, "✅ Авторизация пройдена")

        # Записываем пользовательское сообщение в память
        try:
            await append_message(chat_id, "user", text)
            await tg_debug(context, chat_id, "🧠 Сообщение добавлено в память")
        except Exception as e:
            await tg_debug(context, chat_id, f"⚠️ Ошибка памяти: {e}")

        # 2) AI agent -> returns json contract
        await tg_debug(context, chat_id, "🤖 Запрос к AI...")
        result = await run_ai_for_text(
            chat_id=chat_id, 
            user_id=user.id if user else None, 
            user_name=user.full_name if user else None, 
            text=text
        )
        await tg_debug(context, chat_id, f"✅ AI ответ получен. send_excel={result.send_excel}, send_card={result.send_card}, chart={bool(result.chart)}")

        # Если включён debug — показываем SQL и первые строки
        try:
            if await is_debug(chat_id):
                if result.sql_query:
                    await tg_debug(context, chat_id, f"<pre>{sanitize_html(result.sql_query)}</pre>")
                if result.table_data:
                    sample = result.table_data[:3]
                    await tg_debug(context, chat_id, f"<code>rows:</code> {sanitize_html(str(sample))}")
        except Exception:
            pass

        # 3) Санитизация HTML
        html = sanitize_html(result.output)

        # 4) Логирование -> получение log_id
        log_id = await log_interaction(
            chat_id,
            user.id if user else None,
            user.full_name if user else None,
            text,
            html,
            str(context.application.bot.id),
        )
        await tg_debug(context, chat_id, f"📝 Лог записан id={log_id}")

        # Сохраняем ответ ассистента в память
        try:
            if result.output:
                await append_message(chat_id, "assistant", result.output)
        except Exception:
            pass

        # 5) Обработка специальных действий
        # Гейтинг по ТЗ: график/Excel только по явной просьбе в тексте запроса
        chart_intent = bool(re.search(r"график|диаграмм|линейн|столбчат|кругов|pie|bar|line|doughnut", text.lower()))
        excel_intent = bool(re.search(r"\bexcel\b|эксель|таблиц|в\s+excel|в\s+эксель", text.lower()))

        if result.send_excel and excel_intent:
            await tg_debug(context, chat_id, "📧 Отправка Excel...")
            await handle_excel_request(context, chat_id, result)
            return

        if result.send_card:
            await tg_debug(context, chat_id, f"🗂️ Отправка карточки: {result.rep_name}")
            await handle_card_request(context, chat_id, result)
            return

        # 6) Отправка ответа или графика
        if result.direct_chart and result.chart:
            await tg_debug(context, chat_id, "📊 Генерация графика...")
            
            # Генерируем график
            from src.services.charts.service import render_chart_to_png
            chart_png = render_chart_to_png(result.chart)
            
            # Кнопка обучения
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    text="🚀 Отправить на обучение", 
                    callback_data=f"train:{log_id}"
                )
            ]])
            
            # Отправляем график с кнопкой обучения
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=chart_png,
                reply_markup=keyboard
            )
        else:
            # Обычный текстовый ответ с кнопкой обучения
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    text="🚀 Отправить на обучение", 
                    callback_data=f"train:{log_id}"
                )
            ]])
            
            await context.bot.send_message(
                chat_id=chat_id, 
                text=html, 
                parse_mode=ParseMode.HTML, 
                reply_markup=keyboard
            )
        await tg_debug(context, chat_id, "✅ Ответ отправлен")

    except Exception as e:
        logger.error(f"Error processing text message: {e}", exc_info=True)
        await tg_debug(context, chat_id, f"❌ Ошибка обработки: {e}")
        await context.bot.send_message(
            chat_id=chat_id, 
            text="❌ Произошла ошибка при обработке сообщения"
        )


async def handle_excel_request(context: ContextTypes.DEFAULT_TYPE, chat_id: int, result) -> None:
    """Обработка запроса на отправку Excel"""
    try:
        from src.handlers.excel_flow import send_excel_via_email
        
        recipient = result.recipient or 'default@example.com'
        subject = result.subject or 'Excel Report'
        body = result.body or ''
        
        if result.table_data:
            await send_excel_via_email(recipient, subject, body, result.table_data)
            await context.bot.send_message(
                chat_id=chat_id, 
                text="✅ Excel отправлен на почту"
            )
        else:
            await context.bot.send_message(
                chat_id=chat_id, 
                text="❌ Нет данных для Excel"
            )
    except Exception as e:
        logger.error(f"Error sending Excel: {e}")
        await context.bot.send_message(
            chat_id=chat_id, 
            text="❌ Ошибка отправки Excel"
        )


async def handle_card_request(context: ContextTypes.DEFAULT_TYPE, chat_id: int, result) -> None:
    """Обработка запроса на отправку карточки"""
    try:
        from src.handlers.cards import resolve_card_path
        cards_dir = os.environ.get("CARDS_DIR", "/home/adminvm/cards")

        rep = (result.rep_name or "").strip()

        if rep.lower() == "all":
            # Отправляем все карточки как отдельные документы (упрощённо)
            sent_any = False
            for name in os.listdir(cards_dir):
                if not name.startswith("card_") or not name.endswith(".html"):
                    continue
                path = os.path.join(cards_dir, name)
                try:
                    if os.path.getsize(path) > MAX_FILE_SIZE:
                        continue
                    with open(path, 'rb') as f:
                        await context.bot.send_document(chat_id=chat_id, document=f, filename=name)
                        sent_any = True
                except Exception:
                    continue
            if not sent_any:
                await context.bot.send_message(chat_id=chat_id, text="❌ Не удалось отправить карточки")
            return

        path = resolve_card_path(rep)

        if path and os.path.exists(path):
            # Проверка размера файла
            file_size = os.path.getsize(path)
            if file_size > MAX_FILE_SIZE:
                await context.bot.send_message(
                    chat_id=chat_id, 
                    text="❌ Файл слишком большой"
                )
                return
            with open(path, 'rb') as f:
                await context.bot.send_document(
                    chat_id=chat_id, 
                    document=f, 
                    filename=os.path.basename(path)
                )
        else:
            await context.bot.send_message(
                chat_id=chat_id, 
                text=f"❌ Нет такого торгового: {result.rep_name}"
            )
    except Exception as e:
        logger.error(f"Error sending card: {e}")
        await context.bot.send_message(
            chat_id=chat_id, 
            text="❌ Ошибка отправки карточки"
        )


async def handle_chart_request(context: ContextTypes.DEFAULT_TYPE, chat_id: int, result) -> None:
    """Обработка запроса на отправку графика"""
    try:
        from src.services.charts.service import render_chart_to_png
        
        # Логируем конфигурацию графика для отладки
        logger.info(f"📊 CHART CONFIG: {result.chart}")
        
        chart_png = render_chart_to_png(result.chart)
        await context.bot.send_photo(chat_id=chat_id, photo=chart_png)
    except Exception as e:
        logger.error(f"Error generating chart: {e}")
        await context.bot.send_message(
            chat_id=chat_id, 
            text="❌ Ошибка генерации графика"
        )
