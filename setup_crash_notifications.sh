#!/bin/bash

# Скрипт для настройки уведомлений о падении бота

echo "=== Настройка уведомлений о падении бота ==="
echo ""

# Проверить, что config.env существует
if [ ! -f config.env ]; then
    echo "❌ Файл config.env не найден!"
    exit 1
fi

# Chat ID уже указан в notify_bot_crash.sh (802114947)
echo "Chat ID администратора: 802114947"
echo ""

# Сделать скрипт исполняемым
chmod +x notify_bot_crash.sh

# Создать файл логов
sudo touch /var/log/telegram-bot-crashes.log
sudo chown tarasov:tarasov /var/log/telegram-bot-crashes.log

# Создать основные лог файлы если их нет
sudo touch /var/log/telegram-bot.log
sudo touch /var/log/telegram-bot-error.log
sudo chown tarasov:tarasov /var/log/telegram-bot.log
sudo chown tarasov:tarasov /var/log/telegram-bot-error.log

# Скопировать файлы сервисов
echo "Копирование файлов systemd..."
sudo cp telegram-bot.service /etc/systemd/system/
sudo cp telegram-bot-crash-notify.service /etc/systemd/system/

# Перезагрузить systemd
echo "Перезагрузка systemd..."
sudo systemctl daemon-reload

# Включить автозапуск
echo "Включение автозапуска..."
sudo systemctl enable telegram-bot.service

echo ""
echo "✅ Настройка завершена!"
echo ""
echo "Теперь при падении бота вы получите уведомление на Telegram Chat ID: 802114947"
echo ""
echo "Управление ботом:"
echo "  Запустить:      sudo systemctl start telegram-bot"
echo "  Остановить:     sudo systemctl stop telegram-bot"
echo "  Перезапустить:  sudo systemctl restart telegram-bot"
echo "  Статус:         sudo systemctl status telegram-bot"
echo "  Логи:           sudo journalctl -u telegram-bot -f"
echo ""
echo "Проверить уведомления:"
echo "  Логи крэшей:    tail -f /var/log/telegram-bot-crashes.log"
