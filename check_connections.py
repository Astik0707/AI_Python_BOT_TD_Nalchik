#!/usr/bin/env python3
"""
Скрипт проверки подключений к сервисам
"""
import os
import sys
import asyncio
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

async def check_postgresql():
    """Проверка подключения к PostgreSQL"""
    print("🔍 Проверка PostgreSQL...")
    try:
        import asyncpg
        conn = await asyncpg.connect(
            host=os.environ.get('PG_HOST'),
            port=int(os.environ.get('PG_PORT', '5432')), 
            database=os.environ.get('PG_DB'),
            user=os.environ.get('PG_USER'),
            password=os.environ.get('PG_PASSWORD'),
            ssl=os.environ.get('PG_SSLMODE', 'prefer') == 'require',
            command_timeout=5
        )
        
        version = await conn.fetchval('SELECT version();')
        print(f"✅ PostgreSQL OK: {version[:70]}...")
        
        # Проверяем наличие критичных таблиц
        tables = ['bot_autorized_chats', 'agent_logs', 'training_clicks', 'clients', 'profit']
        for table in tables:
            exists = await conn.fetchval(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = $1);",
                table
            )
            status = "✅" if exists else "❌"
            print(f"  {status} Таблица {table}: {'найдена' if exists else 'НЕ НАЙДЕНА'}")
        
        await conn.close()
        return True
    except Exception as e:
        print(f"❌ PostgreSQL ERROR: {e}")
        return False

def check_openai():
    """Проверка подключения к OpenAI API"""
    print("\n🔍 Проверка OpenAI API...")
    try:
        from openai import OpenAI
        base_url = os.getenv('OPENAI_BASE_URL')
        if base_url:
            client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'), base_url=base_url)
            print(f"✅ Используется VPN прокси: {base_url}")
        else:
            client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
            print("✅ Используется стандартный OpenAI API")
        
        # Проверяем доступность API
        models = client.models.list()
        print("✅ OpenAI API OK: доступ к API работает")
        
        # Проверяем наличие нужных моделей
        model_names = [m.id for m in models.data]
        chat_model = os.getenv('OPENAI_MODEL_CHAT', 'gpt-4')
        whisper_model = os.getenv('OPENAI_MODEL_WHISPER', 'whisper-1')
        
        if chat_model in model_names or 'gpt-4' in model_names:
            print(f"✅ Chat модель доступна: {chat_model}")
        else:
            print(f"⚠️ Chat модель {chat_model} не найдена, но API работает")
            
        print(f"✅ Whisper модель: {whisper_model} (стандартная)")
        return True
    except Exception as e:
        print(f"❌ OpenAI API ERROR: {e}")
        return False

def check_redis():
    """Проверка подключения к Redis (опционально)"""
    print("\n🔍 Проверка Redis...")
    try:
        import redis
        r = redis.Redis(
            host=os.environ.get('REDIS_HOST', 'localhost'),
            port=int(os.environ.get('REDIS_PORT', 6379)),
            db=int(os.environ.get('REDIS_DB', 0)),
            password=os.environ.get('REDIS_PASSWORD') or None,
            socket_connect_timeout=3
        )
        r.ping()
        print("✅ Redis OK: подключение работает")
        return True
    except Exception as e:
        print(f"⚠️ Redis недоступен: {e}")
        print("   Redis не критичен для работы бота")
        return False

def check_environment():
    """Проверка переменных окружения"""
    print("\n🔍 Проверка переменных окружения...")
    required_vars = [
        'TELEGRAM_BOT_TOKEN',
        'OPENAI_API_KEY',
        'PG_HOST',
        'PG_USER',
        'PG_PASSWORD',
        'PG_DB'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Отсутствуют переменные: {', '.join(missing_vars)}")
        return False
    else:
        print("✅ Все необходимые переменные окружения установлены")
        return True

async def main():
    """Главная функция проверки"""
    print("🚀 Проверка подключений Test_Bot_n8n")
    print("=" * 50)
    
    # Проверяем переменные окружения
    env_ok = check_environment()
    
    # Проверяем PostgreSQL
    pg_ok = await check_postgresql()
    
    # Проверяем OpenAI
    openai_ok = check_openai()
    
    # Проверяем Redis (опционально)
    redis_ok = check_redis()
    
    print("\n" + "=" * 50)
    print("📊 РЕЗУЛЬТАТЫ ПРОВЕРКИ:")
    print(f"   Переменные окружения: {'✅' if env_ok else '❌'}")
    print(f"   PostgreSQL: {'✅' if pg_ok else '❌'}")
    print(f"   OpenAI API: {'✅' if openai_ok else '❌'}")
    print(f"   Redis: {'✅' if redis_ok else '⚠️'}")
    
    if env_ok and pg_ok and openai_ok:
        print("\n🎉 Все критические сервисы работают! Бот готов к запуску.")
        return True
    else:
        print("\n❌ Есть проблемы с подключениями. Исправьте ошибки перед запуском.")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
