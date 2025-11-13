# 🚀 Quick Start Guide

## Минимальная установка (5 минут)

### 1. Установить зависимости

```bash
cd hackathon-dont-touch-the-grass-enjoyers
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Настроить PostgreSQL

```bash
# Создать базу данных вручную
createdb telegram_bot
```

### 3. Настроить config.env

Обязательно укажите:
- `TELEGRAM_BOT_TOKEN` - от @BotFather
- `OPENROUTER_API_KEY` - от https://openrouter.ai/keys  
- `DB_USER` - ваше имя пользователя PostgreSQL (обычно совпадает с системным именем)
- `DB_PASSWORD` - оставьте пустым если не требуется

### 4. Запустить бота

**На macOS (M1/M2/M3):**
```bash
./run_bot.sh
```

**Или напрямую:**
```bash
source venv/bin/activate
arch -arm64 python bot.py
```

**На Linux/Windows:**
```bash
source venv/bin/activate  # Linux/macOS
# или venv\Scripts\activate  # Windows
python bot.py
```

## ✅ Проверка

Бот должен вывести:
```
INFO - Configuration validated successfully
INFO - Database connected successfully
INFO - 🚀 Bot is starting...
```

Откройте Telegram и напишите боту `/start`

## 🐛 Если что-то не работает

### Бот зависает при запуске
**На macOS:** Используйте `./run_bot.sh` или `arch -arm64 python bot.py`
Проблема: Python работает в режиме Rosetta (x86_64), а psycopg2 собран для ARM64

### PostgreSQL не запущен
```bash
# macOS
brew services start postgresql

# Linux
sudo systemctl start postgresql
sudo systemctl status postgresql
```

### Ошибка подключения к БД
Проверьте `config.env`:
- DB_USER должен быть вашим именем пользователя системы
- DB_PASSWORD оставьте пустым если не установлен
- DB_HOST=localhost
- DB_PORT=5432
- Убедитесь что база данных создана: `createdb telegram_bot`

### Bot token invalid
Получите новый токен от @BotFather:
1. Напишите `/newbot`
2. Следуйте инструкциям
3. Скопируйте токен в `config.env`

### OpenRouter API error
1. Проверьте баланс: https://openrouter.ai/credits
2. Проверьте ключ: https://openrouter.ai/keys
3. Убедитесь что ключ начинается с `sk-or-v1-`

## 📊 Полезные команды

```bash
# Проверить БД
psql -U postgres -d telegram_bot
SELECT * FROM users;

# Посмотреть логи
python bot.py | tee bot.log

# Остановить бота
Ctrl+C
```

## 📖 Дальше

См. [SETUP.md](SETUP.md) для подробной документации.

