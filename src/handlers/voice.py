from __future__ import annotations
from telegram import Update
from telegram.ext import ContextTypes

from src.ai.transcribe import transcribe_voice
from src.utils.logger import get_logger
from src.db.auth import check_authorized_chat

logger = get_logger("handlers.voice")


async def process_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик голосовых сообщений"""
    try:
        # Авторизация
        if not await check_authorized_chat(update.effective_chat.id):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ У вас нет доступа к этому боту"
            )
            return

        voice = update.effective_message.voice
        if not voice:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Не удалось получить голосовое сообщение"
            )
            return

        # Проверка размера файла (максимум 20MB для голосовых)
        if voice.file_size and voice.file_size > 20 * 1024 * 1024:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Голосовое сообщение слишком большое (максимум 20MB)"
            )
            return

        # Отправляем сообщение о начале обработки
        processing_msg = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🎤 Обрабатываю голосовое сообщение..."
        )

        try:
            # Получаем файл
            file = await context.bot.get_file(voice.file_id)
            
            # Транскрибируем
            text = await transcribe_voice(file.file_path)
            
            if text:
                # Удаляем сообщение о обработке
                await processing_msg.delete()
                
                # Отправляем транскрибированный текст
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"📝 <b>Транскрибированный текст:</b>\n\n{text}",
                    parse_mode="HTML"
                )
                
                # Обрабатываем как обычное текстовое сообщение
                from src.handlers.text import process_text
                update.effective_message.text = text
                await process_text(update, context)
            else:
                await processing_msg.edit_text("❌ Не удалось распознать речь")
                
        except Exception as e:
            logger.error(f"Error processing voice message: {e}")
            await processing_msg.edit_text("❌ Ошибка обработки голосового сообщения")

    except Exception as e:
        logger.error(f"Error in voice handler: {e}", exc_info=True)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Произошла ошибка при обработке голосового сообщения"
        )
