from __future__ import annotations
from typing import List, Dict, Any
from src.services.excel.service import build_excel_bytes
from src.services.mail.service import send_email, _resolve_recipient


async def send_excel_via_email(recipient: str, subject: str, body: str, table_data: List[Dict[str, Any]]):
    excel_bytes = build_excel_bytes(table_data)
    # Разрешаем получателя через БД (если передано не email)
    resolved = await _resolve_recipient(recipient)
    send_email(
        recipient=resolved,
        subject=subject or 'Без темы',
        body=body or '',
        attachments=[('report.xlsx', excel_bytes, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')]
    )
