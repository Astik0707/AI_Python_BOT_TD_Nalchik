from __future__ import annotations
import os
from typing import List, Dict, Any
from src.services.excel.service import build_excel_bytes
from src.services.excel.script_runner import build_excel_bytes_via_script
from src.services.mail.service import send_email, _resolve_recipient
from src.utils.logger import get_logger

logger = get_logger("excel_flow")


async def send_excel_via_email(recipient: str, subject: str, body: str, table_data: List[Dict[str, Any]]):
    # Always use external script for beautiful formatted Excel
    try:
        _, excel_bytes = build_excel_bytes_via_script(table_data)
        logger.info("✅ Excel generated via external script for email")
    except Exception as e:
        logger.warning(f"⚠️ External script failed for email: {e}, using fallback")
        excel_bytes = build_excel_bytes(table_data)
    # Разрешаем получателя через БД (если передано не email)
    resolved = await _resolve_recipient(recipient)
    send_email(
        recipient=resolved,
        subject=subject or 'Без темы',
        body=body or '',
        attachments=[('report.xlsx', excel_bytes, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')]
    )


async def send_excel_in_chat(context, chat_id: int, table_data: List[Dict[str, Any]]):
    """Generate excel and send as Telegram document to the chat."""
    # Always use external script for beautiful formatted Excel
    path = None
    data = None
    try:
        path, data = build_excel_bytes_via_script(table_data)
        logger.info(f"✅ Excel generated via external script: {path}")
    except Exception as e:
        logger.warning(f"⚠️ External script failed: {e}, using fallback")
        data = build_excel_bytes(table_data)
    
    if data is None:
        await context.bot.send_message(chat_id=chat_id, text="❌ Не удалось сформировать Excel")
        return
    
    try:
        # Always send from file path if available for better formatting
        if path and os.path.exists(path):
            with open(path, 'rb') as f:
                await context.bot.send_document(chat_id=chat_id, document=f, filename='report.xlsx')
                logger.info("📧 Excel sent to chat via file path")
                return
        
        # Fallback: send from memory
        from io import BytesIO
        await context.bot.send_document(chat_id=chat_id, document=BytesIO(data), filename='report.xlsx')
        logger.info("📧 Excel sent to chat via BytesIO")
    except Exception as e:
        logger.error(f"❌ Error sending Excel to chat: {e}")
        await context.bot.send_message(chat_id=chat_id, text="❌ Ошибка отправки файла в чат")
