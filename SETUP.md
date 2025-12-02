# 🚀 Быстрая установка и запуск

> Краткая инструкция для запуска бота

## 📋 Требования

- **Python:** 3.10+
- **PostgreSQL:** 12+
- **RAM:** Минимум 512 MB

## ⚡ Быстрый старт

### 1. Клонирование и настройка окружения

```bash
git clone https://github.com/AMaslov01/hackathon-dont-touch-the-grass-enjoyers

cd hackathon-dont-touch-the-grass-enjoyers

python3 -m venv venv

source venv/bin/activate  # Linux/macOS/WSL или venv\Scripts\activate для Windows

pip install -r requirements.txt
```

### 2. Настройка конфигурации

Создайте файл `config.env` в корне проекта:

```env
# Telegram Bot Token - Get from @BotFather on Telegram
TELEGRAM_BOT_TOKEN=__

# OpenRouter API Key - Get from https://openrouter.ai/keys
OPENROUTER_API_KEY=__

# OpenRouter API URL
OPENROUTER_API_URL=https://openrouter.ai/api/v1/chat/completions

# AI Model to use
AI_MODEL=z-ai/glm-4.5-air:free

# PostgreSQL Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=telegram_bot
DB_USER=postgres
DB_PASSWORD=postgres

```

### 3. Запуск PostgreSQL и настройка БД

```bash
#Установите PostgreSQL
sudo apt install postgresql #Linux/WSL
# Запустите PostgreSQL (если еще не запущен)
sudo service postgresql start  # Linux/WSL
# или 
brew services start postgresql  # macOS

# Установите пароль для пользователя postgres (если не установлен)
sudo -u postgres psql -c "ALTER USER postgres WITH PASSWORD 'postgres';"

# Создать базу данных
psql -U postgres -h localhost -p 5432
CREATE DATABASE telegram_bot;
\q

# Загрузить схему
psql -U postgres -d telegram_bot -h localhost -p 5432 -f schema.sql

```

### 4. Запуск бота

```bash
python bot.py
```



