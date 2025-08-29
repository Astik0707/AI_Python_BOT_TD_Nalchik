from __future__ import annotations
from src.db.pool import execute


async def log_training_click(log_id: int, chat_id: int, clicked_by: int) -> None:
    """Записать клик по кнопке обучения (совместимо с n8n-схемой)."""
    try:
        await execute(
            """
            INSERT INTO public.training_clicks (log_id, chat_id, clicked_by, status, clicked_at)
            VALUES ($1, $2, $3, 'в очереди', NOW());
            """,
            (log_id, chat_id, clicked_by)
        )
    except Exception as e:
        import logging
        logging.getLogger("training").error(f"Failed to log training click: {e}")