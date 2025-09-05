from __future__ import annotations
import asyncio
import os
from dataclasses import dataclass
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
)

from src.utils.html_sanitize import sanitize_html
from src.handlers.router import handle_text_message, handle_voice_message
from src.handlers.inline_handlers import handle_card_callback
from src.handlers.training_feedback import handle_training_feedback, handle_comment_form
from src.utils.logger import setup_logging, get_logger
from src.db.pool import close_pool
from src.utils.debug import set_debug, is_debug
 

load_dotenv(dotenv_path=os.path.join(os.getcwd(), ".env"), override=True)

# Настройка логирования
setup_logging()
logger = get_logger("bot")

@dataclass
class Settings:
    telegram_token: str
    polling_interval: float


def read_settings() -> Settings:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
    return Settings(
        telegram_token=token,
        polling_interval=float(os.environ.get("POLLING_INTERVAL_SECONDS", "5")),
    )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    try:
        help_html = (
            "<b>Аналитический бот готов к работе.</b>\n\n"
            "Примеры запросов:\n"
            "— Продажи по менеджерам за прошлый месяц\n"
            "— АКБ по регионам за текущий квартал\n"
            "— Динамика выручки по брендам за 3 месяца\n"
            "— Карточка торгового Альборов Феликс Олегович\n"
            "— Отправь это в Excel Иванову\n\n"
            "Подсказки:\n"
            "— Для Excel напишите: отправь в Excel/эксель/таблицей кому-то\n"
            "— Кнопка \"🚀 Отправить на обучение\" добавляется к каждому ответу\n\n"
            "Команды:\n"
            "• /debug_on, /debug_off — включить/выключить отладку\n"
            "• /refresh_refs — обновить справочники из БД\n"
            "• /refs_stats — статистика справочников"
        )
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=help_html,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Error in start command: {e}")


async def debug_on(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    await set_debug(chat_id, True)
    await context.bot.send_message(chat_id=chat_id, text="🔧 Режим отладки включён для этого чата")


async def debug_off(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    await set_debug(chat_id, False)
    await context.bot.send_message(chat_id=chat_id, text="✅ Режим отладки выключен")


async def show_cards_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню с карточками торговых представителей."""
    chat_id = update.effective_chat.id
    try:
        from src.handlers.inline_handlers import show_cards_menu
        await show_cards_menu(context, chat_id)
    except Exception as e:
        logger.error(f"❌ Ошибка показа меню карточек: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ Ошибка при создании меню карточек"
        )


 


def main() -> None:
    """Главная функция приложения (синхронная для корректной работы run_polling)."""
    try:
        settings = read_settings()

        telegram_base_url = os.getenv("TELEGRAM_API_BASE_URL")
        if telegram_base_url:
            app = Application.builder().token(settings.telegram_token).base_url(telegram_base_url).build()
            logger.info(f"Using Telegram API proxy: {telegram_base_url}")
        else:
            app = Application.builder().token(settings.telegram_token).build()
            logger.info("Using standard Telegram API")

        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("debug_on", debug_on))
        app.add_handler(CommandHandler("debug_off", debug_off))
        
        app.add_handler(CommandHandler("cards", show_cards_command))
        app.add_handler(CallbackQueryHandler(handle_card_callback, pattern="^card_"))
        app.add_handler(CallbackQueryHandler(handle_training_feedback, pattern="^training_"))
        app.add_handler(CallbackQueryHandler(handle_comment_form, pattern="^comment_"))
        app.add_handler(MessageHandler(filters.VOICE, handle_voice_message))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

        # Инициализируем справочники при запуске
        # Убираем проблемный код с отдельным потоком и event loop
        try:
            # Простая синхронная инициализация без event loop
            import time
            time.sleep(0.1)  # Небольшая пауза для стабилизации
            logger.info("✅ Справочники будут загружены при первом запросе")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации справочников: {e}")
            

        # Убираем проблемный код с threading
        # import threading
        # init_thread = threading.Thread(target=init_references_sync, daemon=True)
        # init_thread.start()
        
        # Ждем немного, чтобы справочники загрузились
        # import time
        # time.sleep(1)

        logger.info("Starting polling (PTB v21 run_polling)...")
        app.run_polling(
            poll_interval=settings.polling_interval,
            allowed_updates=Update.ALL_TYPES
        )

    except Exception as e:
        logger.error(f"Critical error in main: {e}")
        raise
    finally:
        # Закрываем пул соединений БД
        try:
            asyncio.run(close_pool())
        except Exception:
            pass
        logger.info("Application shutdown complete")


if __name__ == "__main__":
    main()
