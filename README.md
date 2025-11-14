# Telegram AI Bot 🤖

Telegram бот с AI интеграцией, системой учетных записей и токенов.

## ✨ Возможности

- 🤖 **AI Ассистент** - Отвечает на любые вопросы используя AI
- 📄 **Финансовый план в PDF** - Генерация профессиональных PDF документов с финансовыми планами
- 👤 **Личный аккаунт** - Автоматически создается для каждого пользователя
- 💰 **Система токенов** - 100 токенов, обновляются каждые 24 часа
- 🗄️ **База данных** - PostgreSQL для надежного хранения данных
- 🇷🇺 **Русский язык** - Все сообщения и ответы на русском
- 📊 **История запросов** - Сохраняется в базе данных

## 🚀 Быстрый старт

### Требования

- Python 3.10+ 
- PostgreSQL 12+
- Telegram Bot Token
- OpenRouter API Key

### Установка

1. **Клонировать репозиторий и перейти в папку**

```bash
cd hackathon-dont-touch-the-grass-enjoyers
```

2. **Создать виртуальное окружение**

```bash
python3 -m venv venv
source venv/bin/activate
```

3. **Установить зависимости**

```bash
pip install -r requirements.txt
```

4. **Настроить PostgreSQL**

```bash
# Создать базу данных
psql -U postgres
CREATE DATABASE telegram_bot;
\q

# Загрузить схему
psql -U postgres -d telegram_bot -f schema.sql
```

5. **Настроить config.env**

Отредактируйте `config.env` файл:

```env
TELEGRAM_BOT_TOKEN=ваш_токен_от_BotFather
OPENROUTER_API_KEY=ваш_ключ_openrouter
DB_PASSWORD=ваш_пароль_postgres
```

6. **Запустить бота**

```bash
python bot.py
```

## 📱 Использование

### Команды бота

- `/start` - Начать работу с ботом
- `/balance` - Проверить баланс токенов  
- `/help` - Получить справку

### Как пользоваться

Просто отправьте текстовое сообщение боту, и он ответит используя AI!

**Примеры:**
```
Что такое Python?
Напиши хокку о программировании
Объясни квантовые компьютеры простыми словами
```

## 💰 Система токенов

- **100 токенов** выдается при первом запуске
- **1 токен** = 1 запрос к AI
- **Автоматическое обновление** каждые 24 часа
- Проверьте баланс командой `/balance`

## 🏗️ Архитектура

```
┌─────────────────┐
│  Telegram User  │
└────────┬────────┘
         │
    ┌────▼────┐
    │  Bot    │
    └────┬────┘
         │
    ┌────▼────────────────┐
    │  User Manager       │
    │  (Tokens & Account) │
    └────┬────────────────┘
         │
    ┌────▼────────┐
    │  AI Client  │
    └────┬────────┘
         │
    ┌────▼───────────┐
    │  OpenRouter AI │
    └────────────────┘
```

## 📂 Структура проекта

```
├── bot.py          # Главное приложение бота
├── ai_client.py    # Клиент для AI API
├── database.py     # Работа с базой данных
├── user_manager.py # Управление пользователями и токенами
├── config.py       # Конфигурация
├── constants.py    # Константы и тексты на русском
├── config.env      # Переменные окружения
├── requirements.txt# Зависимости Python
├── schema.sql      # Схема базы данных
├── SETUP.md        # Подробная инструкция по установке
└── README.md       # Этот файл
```

## 🔧 Настройка

### Изменить количество токенов

Отредактируйте `constants.py`:

```python
TOKEN_CONFIG = {
    "initial_tokens": 100,      # Начальные токены
    "max_tokens": 100,          # Максимум токенов
    "refresh_interval_hours": 24, # Часов до обновления
    "cost_per_request": 1       # Цена запроса
}
```

### Изменить AI модель

Отредактируйте `config.env`:

```env
AI_MODEL=deepseek/deepseek-chat
# Или любая другая модель с https://openrouter.ai/models
```

## 🐛 Решение проблем

### Ошибка подключения к базе данных

```bash
# Проверить, что PostgreSQL запущен
sudo systemctl status postgresql

# Проверить подключение
psql -U postgres -d telegram_bot
```

### Бот не отвечает

1. Проверьте логи: `python bot.py`
2. Проверьте токены в `config.env`
3. Проверьте баланс OpenRouter: https://openrouter.ai/credits

## 📊 Мониторинг

Проверить статистику в базе данных:

```sql
-- Всего пользователей
SELECT COUNT(*) FROM users;

-- Всего запросов
SELECT COUNT(*) FROM usage_history;

-- Топ пользователей
SELECT user_id, username, COUNT(*) as requests
FROM users u 
JOIN usage_history uh ON u.user_id = uh.user_id
GROUP BY u.user_id, u.username
ORDER BY requests DESC
LIMIT 10;
```

## 📝 Технологии

- **Python 3.10+** - Основной язык
- **python-telegram-bot** - Telegram Bot API
- **PostgreSQL** - База данных
- **OpenRouter** - AI API Gateway
- **psycopg2** - PostgreSQL драйвер

## 📄 Лицензия

MIT License

## 🤝 Поддержка

Для подробной инструкции по установке см. [SETUP.md](SETUP.md)

---

Made with ❤️ for Alfa Hackathon
