from __future__ import annotations
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Tuple
from src.db.pool import fetch_one


async def _resolve_recipient(recipient: str) -> str:
    """Разрешить адрес через функцию resolve_sales_rep_email, если recipient не email."""
    try:
        if '@' in (recipient or ''):
            return recipient
        row = await fetch_one("SELECT email FROM public.resolve_sales_rep_email($1);", (recipient,))
        return (row or {}).get('email') or recipient
    except Exception:
        return recipient


def send_email(recipient: str, subject: str, body: str, attachments: List[Tuple[str, bytes, str]] = None):
    """
    Отправляет email с вложениями
    """
    try:
        # Настройки SMTP
        smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        smtp_user = os.environ.get("SMTP_USER")
        smtp_password = os.environ.get("SMTP_PASSWORD")
        
        if not all([smtp_user, smtp_password]):
            raise ValueError("SMTP credentials not configured")
        
        # Создаем сообщение
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = recipient
        msg['Subject'] = subject
        
        # Добавляем текст письма
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # Добавляем вложения
        if attachments:
            for filename, file_data, content_type in attachments:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(file_data)
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {filename}'
                )
                msg.attach(part)
        
        # Отправляем письмо
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        text = msg.as_string()
        server.sendmail(smtp_user, recipient, text)
        server.quit()
        
    except Exception as e:
        # Логируем ошибку
        import logging
        logging.getLogger("mail").error(f"Email sending failed: {e}")
        raise
