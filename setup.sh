#!/usr/bin/env bash
set -euo pipefail

echo "🚀 Настройка Python Telegram бота"

# 1. Создать виртуальное окружение
if [ ! -d .venv ]; then
    echo "📦 Создание виртуального окружения..."
    python3 -m venv .venv
fi

# 2. Активировать и обновить pip
echo "🔧 Обновление pip и установка зависимостей..."
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt

# 3. Создать .env из примера, если не существует
if [ ! -f .env ]; then
    echo "⚙️ Создание .env из шаблона..."
    cat > .env << 'EOF'
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
POLLING_INTERVAL_SECONDS=5
TELEGRAM_API_BASE_URL=

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL_CHAT=gpt-4.1
OPENAI_MODEL_WHISPER=whisper-1
OPENAI_BASE_URL=

# PostgreSQL Database
PG_HOST=localhost
PG_PORT=5432
PG_DB=milk
PG_USER=your_db_user
PG_PASSWORD=your_db_password
PG_SSLMODE=prefer

# Redis Configuration (optional)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# SMTP Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
SMTP_STARTTLS=true

# File Paths
CARDS_DIR=/home/adminvm/cards
WORK_DIR=/home/adminvm/Test_Bot_n8n

# Logging
LOG_LEVEL=INFO
EOF
    echo "❗ ВАЖНО: Отредактируйте .env и укажите токены/пароли!"
fi

# 4. Создать директории для логов
mkdir -p logs

# 5. Проверить подключения
echo "🔍 Проверка подключений..."
if python check_connections.py; then
    echo "✅ Все подключения работают"
else
    echo "⚠️ Есть проблемы с подключениями. Проверьте настройки в .env"
fi

# 6. Установить systemd service (опционально)
read -p "🤖 Установить systemd service? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo cp systemd/bot.service /etc/systemd/system/test-bot-n8n.service
    sudo systemctl daemon-reload
    echo "✅ Systemd service установлен. Для запуска:"
    echo "   sudo systemctl enable test-bot-n8n"
    echo "   sudo systemctl start test-bot-n8n"
fi

echo ""
echo "✅ Установка завершена!"
echo "📝 Следующие шаги:"
echo "   1. Отредактируйте .env (добавьте токены)"
echo "   2. Запустите: ./run.sh"
echo "   Или используйте systemd service"
echo ""
echo "🔧 Для проверки подключений: python check_connections.py"
