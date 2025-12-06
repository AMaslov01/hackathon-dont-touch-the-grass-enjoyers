#!/bin/bash

# Скрипт для отправки уведомления в Telegram при падении бота
# Используется systemd OnFailure

# Загрузить переменные окружения
if [ -f /home/tarasov/hackathon-dont-touch-the-grass-enjoyers/config.env ]; then
    export $(cat /home/tarasov/hackathon-dont-touch-the-grass-enjoyers/config.env | grep -v '^#' | xargs)
fi

# Ваш личный Chat ID для получения уведомлений
# Получить можно через @userinfobot в Telegram
ADMIN_CHAT_ID="802114947"

# Получить последние логи
LOGS=$(sudo journalctl -u telegram-bot -n 50 --no-pager | tail -20)

# Сформировать сообщение
MESSAGE="🚨 БОТ УПАЛ НА СЕРВЕРЕ!

Время: $(date '+%Y-%m-%d %H:%M:%S')
Сервер: $(hostname)

Последние логи:
$LOGS

Systemd автоматически перезапустит бота через 10 секунд."

# Отправить сообщение в Telegram
curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d chat_id="$ADMIN_CHAT_ID" \
    -d text="$MESSAGE" \
    -d parse_mode="HTML" > /dev/null 2>&1

# Логировать
echo "[$(date)] Crash notification sent to admin" >> /var/log/telegram-bot-crashes.log

