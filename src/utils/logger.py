from __future__ import annotations
import os
import logging
import logging.handlers
from typing import Optional


def setup_logging(log_level: Optional[str] = None) -> None:
    """Настройка структурированного логирования"""
    if log_level is None:
        log_level = os.getenv("LOG_LEVEL", "INFO")
    
    # Создаём директорию для логов
    os.makedirs("logs", exist_ok=True)
    
    # Настройка форматирования
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Основной логгер
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Очищаем существующие обработчики
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Файловый обработчик с ротацией
    file_handler = logging.handlers.RotatingFileHandler(
        "logs/bot.log",
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Обработчик ошибок
    error_handler = logging.handlers.RotatingFileHandler(
        "logs/errors.log",
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3,
        encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)


def get_logger(name: str) -> logging.Logger:
    """Получить логгер с указанным именем"""
    return logging.getLogger(name)
