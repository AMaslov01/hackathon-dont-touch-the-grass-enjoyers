#!/home/tarasov/hackathon-dont-touch-the-grass-enjoyers/venv/bin/python
"""
Healthcheck скрипт для мониторинга бота
Можно использовать с внешними сервисами типа healthchecks.io
"""

import os
import sys
import requests
from datetime import datetime

# URL healthcheck сервиса (например, https://healthchecks.io)
# Получите свой URL на https://healthchecks.io после регистрации
HEALTHCHECK_URL = os.getenv('HEALTHCHECK_URL', '')

# Проверить, работает ли бот
def check_bot_running():
    """Проверить, что процесс бота запущен"""
    import subprocess
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'python bot.py'],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        print(f"Error checking bot process: {e}")
        return False

def check_telegram_api():
    """Проверить, что бот может подключиться к Telegram API"""
    try:
        from config import Config
        url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/getMe"
        response = requests.get(url, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Error checking Telegram API: {e}")
        return False

def send_healthcheck():
    """Отправить ping на healthcheck сервис"""
    if not HEALTHCHECK_URL:
        return
    
    try:
        requests.get(HEALTHCHECK_URL, timeout=10)
        print(f"[{datetime.now()}] Healthcheck ping sent")
    except Exception as e:
        print(f"[{datetime.now()}] Failed to send healthcheck: {e}")

def main():
    """Главная функция проверки"""
    
    # Проверить процесс
    process_ok = check_bot_running()
    if not process_ok:
        print(f"❌ Bot process is not running!")
        sys.exit(1)
    
    # Проверить API
    api_ok = check_telegram_api()
    if not api_ok:
        print(f"❌ Cannot connect to Telegram API!")
        sys.exit(1)
    
    print(f"✅ Bot is healthy")
    
    # Отправить ping на внешний сервис
    send_healthcheck()
    
    sys.exit(0)

if __name__ == '__main__':
    main()

