from __future__ import annotations
import os
import aiohttp
import aiofiles
from openai import AsyncOpenAI
from src.utils.logger import get_logger

logger = get_logger("ai.transcribe")


async def transcribe_voice(file_path: str) -> str:
    """Транскрибировать голосовое сообщение через Whisper API"""
    try:
        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        model = os.environ.get("OPENAI_MODEL_WHISPER", "whisper-1")

        # Скачиваем файл во временную директорию
        temp_file_path = f"/tmp/voice_{os.getpid()}_{os.path.basename(file_path)}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(file_path) as response:
                if response.status != 200:
                    logger.error(f"Failed to download voice file: {response.status}")
                    return ""
                
                async with aiofiles.open(temp_file_path, 'wb') as f:
                    await f.write(await response.read())

        try:
            # Транскрибируем через OpenAI
            with open(temp_file_path, 'rb') as audio_file:
                transcript = await client.audio.transcriptions.create(
                    model=model,
                    file=audio_file,
                    language="ru"
                )
            
            return transcript.text.strip()
            
        finally:
            # Удаляем временный файл
            try:
                os.remove(temp_file_path)
            except OSError:
                pass  # Игнорируем ошибки удаления
                
    except Exception as e:
        logger.error(f"Error transcribing voice: {e}")
        return ""
