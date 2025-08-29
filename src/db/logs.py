from __future__ import annotations
from typing import Optional
from src.db.pool import execute_returning


async def log_interaction(
    chat_id: int,
    user_id: Optional[int],
    user_name: Optional[str],
    user_message: str,
    bot_response: str,
    bot_id: str,
) -> Optional[int]:
    """Записать взаимодействие в лог"""
    try:
        # Совместимость со старой схемой: user_request, agent_response, n8n_execution
        row = await execute_returning(
            """
            INSERT INTO public.agent_logs (chat_id, user_id, user_name, user_request, agent_response, n8n_execution)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id;
            """,
            (chat_id, user_id, user_name, user_message, bot_response, bot_id)
        )
        return row["id"] if row else None
    except Exception as e:
        import logging
        logging.getLogger("logs").error(f"Failed to log interaction: {e}")
        return None
