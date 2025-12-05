# 🚀 Быстрый старт

## Локальная разработка

### 1. Создать виртуальное окружение
```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Установить зависимости
```bash
pip install -r requirements.txt
```

### 3. Проверить конфиг
```bash
nano config.env  # Проверить TELEGRAM_BOT_TOKEN и настройки БД
```

### 4. Создать базу данных
```bash
sudo -u postgres psql -c "CREATE DATABASE telegram_bot;"
sudo -u postgres psql -d telegram_bot < schema.sql
```

### 5. Загрузить тестовые данные в RAG
```bash
./load_documents.sh test_documents
```

### 6. Запустить бота
```bash
python3 bot.py
```

**При первом запуске с AI_MODE=local:**
- Модель (~5GB) скачается автоматически из HuggingFace
- Это займёт 5-15 минут в зависимости от скорости интернета
- Модель сохранится в папку `./models/` для последующих запусков

---

## 📡 Деплой на Ubuntu сервер

### Способ 1: Git (рекомендуется)

```bash
# На сервере
cd ~
git clone https://github.com/your-repo/hackathon-bot.git
cd hackathon-bot

# Создать виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Установить зависимости
pip install -r requirements.txt

# Проверить конфиг (уже настроен)
nano config.env  # Убедиться что TELEGRAM_BOT_TOKEN и БД настроены

# Создать БД
sudo -u postgres psql -c "CREATE DATABASE telegram_bot;"
sudo -u postgres psql -d telegram_bot < schema.sql

# Загрузить данные в RAG
chmod +x load_documents.sh
./load_documents.sh test_documents

# Запустить (модель скачается автоматически при первом запуске)
python3 bot.py
```

### Способ 2: SCP (копирование файлов)

```bash
# На локальной машине
# Создать архив (исключая ненужное)
tar -czf bot.tar.gz \
  --exclude=rag_data \
  --exclude=venv \
  --exclude=__pycache__ \
  --exclude=*.pyc \
  --exclude=.git \
  .

# Отправить на сервер
scp bot.tar.gz user@your-server.com:~/

# На сервере
ssh user@your-server.com
cd ~
tar -xzf bot.tar.gz
cd hackathon-dont-touch-the-grass-enjoyers

# Создать venv и установить зависимости
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Дальше создать БД, загрузить данные в RAG, запустить
```

### Способ 3: rsync (синхронизация)

```bash
# На локальной машине
rsync -avz --exclude 'rag_data' \
           --exclude 'venv' \
           --exclude '__pycache__' \
           --exclude '*.pyc' \
           --exclude '.git' \
           ./ user@your-server.com:~/hackathon-bot/

# На сервере - создать venv и дальше как в Способе 1
```

---

## 🔄 Запуск в фоне (systemd)

Создать сервис для автозапуска:

```bash
# Создать файл сервиса
sudo nano /etc/systemd/system/telegram-bot.service
```

Содержимое файла:
```ini
[Unit]
Description=Telegram Bot
After=network.target postgresql.service

[Service]
Type=simple
User=your_user
WorkingDirectory=/home/your_user/hackathon-bot
Environment="PATH=/usr/bin:/usr/local/bin"
ExecStart=/usr/bin/python3 /home/your_user/hackathon-bot/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Запустить сервис:
```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot

# Проверить статус
sudo systemctl status telegram-bot

# Посмотреть логи
sudo journalctl -u telegram-bot -f
```

---

## 📚 Работа с RAG

### Загрузка документов

#### Один файл
```bash
# Загрузить один документ из test_documents
python3 rag_tools/add_documents.py test_documents/test_data.txt

# Или загрузить свои документы
python3 rag_tools/add_documents.py my_document.pdf
python3 rag_tools/add_documents.py financial_report.docx
python3 rag_tools/add_documents.py sales_data.xlsx
```

#### Быстрый способ (рекомендуется)
```bash
# Загрузить всю папку test_documents (автоматически рекурсивно)
./load_documents.sh test_documents

# Загрузить один файл
./load_documents.sh test_documents/test_data.txt

# С семантическим чанкингом (качественнее, медленнее)
./load_documents.sh test_documents --semantic

# Загрузить свою папку
./load_documents.sh /path/to/your/documents

# Загрузить свой файл
./load_documents.sh /path/to/document.pdf
```

#### Напрямую через Python
```bash
# Загрузить тестовые документы (только текущая папка)
python3 rag_tools/add_documents.py test_documents

# Загрузить тестовые документы включая подпапки (рекурсивно)
python3 rag_tools/add_documents.py test_documents --recursive

# С семантическим чанкингом (качественнее, но медленнее)
python3 rag_tools/add_documents.py test_documents --semantic --recursive

# Для своих документов используйте полный путь
python3 rag_tools/add_documents.py /path/to/your/documents --recursive
```

### Поддерживаемые форматы
- **Документы:** PDF, DOCX, DOC
- **Таблицы:** XLSX, XLS
- **Текст:** TXT, MD (Markdown)
- **Другие:** HTML, JSON

### Проверка RAG

```bash
# Статистика
python3 rag_tools/manage_rag.py stats

# Тестирование поиска
python3 rag_tools/manage_rag.py test
```

### Тестирование в боте

После загрузки `test_data.txt` спросите у бота:
- "Какой ВВП России?"
- "Какая инфляция в 2023?"
- "Крупнейшие экономики мира?"
- "Какая ключевая ставка ЦБ?"

Бот должен находить ответы в загруженном документе.

---

## 🔧 Режимы AI

### Local LLM (по умолчанию, бесплатно)
```env
AI_MODE=local
LOCAL_MODEL_THREADS=16  # CPU потоков (настроить под сервер)
```

**Первый запуск:**
- Модель Llama-3-8B-Finance (~5GB) скачается автоматически
- Сохранится в `./models/` для повторного использования
- Требует ~8GB RAM и хороший CPU

### OpenRouter (альтернатива, платно)
```env
AI_MODE=openrouter
OPENROUTER_API_KEY=your_key
AI_MODEL=z-ai/glm-4.5-air:free
```

---

## 🐛 Решение проблем

### RAG не работает
```bash
source venv/bin/activate
python -c "from ragBaseMaker.rag_system import RAGSystem; print('OK')"
python rag_tools/manage_rag.py --stats
```

### БД не подключается
```bash
sudo systemctl status postgresql
psql -U postgres -d telegram_bot -c "SELECT 1;"
```

### Бот не запускается
```bash
# Проверить конфиг
source venv/bin/activate
python3 -c "from config import Config; Config.validate()"

# Посмотреть логи
python3 bot.py
```

---

## 📋 Основные команды бота

- `/start` - Начать работу
- `/balance` - Баланс токенов  
- `/help` - Справка
- Просто напишите вопрос - бот будет использовать RAG для поиска ответа

**Готово! 🎉**
