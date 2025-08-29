from __future__ import annotations
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.handlers.text import process_text
from src.handlers.voice import process_voice
from src.handlers.callback import process_callback


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await process_text(update, context)


async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await process_voice(update, context)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await process_callback(update, context)
