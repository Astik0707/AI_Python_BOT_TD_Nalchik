from __future__ import annotations
from telegram import Update
from telegram.ext import ContextTypes

from src.db.training import log_training_click
from src.utils.logger import get_logger
from src.db.auth import check_authorized_chat

logger = get_logger("handlers.callback")


async def process_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик callback-кнопок"""
    try:
        query = update.callback_query
        if not query:
            return

        # Авторизация
        chat_id = query.message.chat_id if query.message else None
        if chat_id is not None:
            if not await check_authorized_chat(chat_id):
                await query.answer()
                return

        await query.answer()

        if query.data.startswith("train:"):
            log_id_str = query.data.split(":")[1]
            try:
                log_id = int(log_id_str)
                chat_id = query.message.chat_id
                clicked_by = query.from_user.id if query.from_user else chat_id

                # Сообщение о принятии в очередь (как в n8n)
                pending_msg = await context.bot.send_message(
                    chat_id=chat_id,
                    text="Ваш запрос принят в работу, ожидайте"
                )

                await log_training_click(log_id, chat_id, clicked_by)

                # Имитация завершения стадии очереди: удаляем pending-сообщение и сообщаем об успехе
                try:
                    await pending_msg.delete()
                except Exception:
                    pass

                await context.bot.send_message(
                    chat_id=chat_id,
                    text="✅ Запрос отправлен на обучение!"
                )
            except ValueError:
                logger.error(f"Invalid log_id in callback: {log_id_str}")
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text="❌ Ошибка обработки запроса"
                )
            except Exception as e:
                logger.error(f"Error logging training click: {e}")
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text="❌ Ошибка отправки на обучение"
                )

    except Exception as e:
        logger.error(f"Error processing callback: {e}", exc_info=True)
        if update.callback_query:
            await update.callback_query.answer("Произошла ошибка")
