from __future__ import annotations
import asyncio
import os
from dataclasses import dataclass
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

from src.utils.html_sanitize import sanitize_html
from src.handlers.router import handle_text_message, handle_voice_message, handle_callback
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
            "— Динамика выручки по брендам за 3 месяца (график)\n"
            "— Карточка торгового Альборов Феликс Олегович\n"
            "— Отправь это в Excel Иванову\n\n"
            "Подсказки:\n"
            "— Для графика явно напишите: график/диаграмма/линейный/столбчатый/круговая\n"
            "— Для Excel напишите: отправь в Excel/эксель/таблицей кому-то\n"
            "— Кнопка \"🚀 Отправить на обучение\" добавляется к каждому ответу\n\n"
            "Команды: /debug_on, /debug_off — включить/выключить отладку"
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
        app.add_handler(CallbackQueryHandler(handle_callback))
        app.add_handler(MessageHandler(filters.VOICE, handle_voice_message))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

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
