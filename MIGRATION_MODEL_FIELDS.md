# Миграция: Разделение полей для локальных и облачных моделей

## Проблема
При переключении режима работы бота (AI_MODE) между `local` и `openrouter` возникала проблема:
- Пользователи, созданные в режиме `local`, имели записанную локальную модель
- При переключении на `openrouter` эта локальная модель оставалась и вызывала конфликты

## Решение
Добавлены два отдельных поля для хранения предпочтений пользователя:
- `current_local_model` - предпочитаемая локальная модель
- `current_cloud_model` - предпочитаемая облачная модель

Теперь при переключении режима бот автоматически использует соответствующее поле.

## Как применить миграцию

### Вариант 1: Через psql
```bash
psql -U postgres -d telegram_bot -f migrations/add_separate_model_fields.sql
```

### Вариант 2: Через Python скрипт
```bash
python3 << 'EOF'
import psycopg2
from config import Config

conn = psycopg2.connect(
    host=Config.DB_HOST,
    port=Config.DB_PORT,
    database=Config.DB_NAME,
    user=Config.DB_USER,
    password=Config.DB_PASSWORD
)

with open('migrations/add_separate_model_fields.sql', 'r') as f:
    sql = f.read()
    
with conn.cursor() as cursor:
    cursor.execute(sql)
    
conn.commit()
conn.close()
print("✅ Migration applied successfully!")
EOF
```

## Что изменилось в коде

### database.py
- `get_user_model(user_id, ai_mode)` - теперь принимает параметр `ai_mode` и возвращает модель из соответствующего поля
- `set_user_model(user_id, model_id, ai_mode)` - сохраняет модель в правильное поле в зависимости от типа модели

### user_manager.py
- Методы `get_user_model()` и `set_user_model()` обновлены для работы с новой логикой

### schema.sql
- Добавлены поля `current_local_model` и `current_cloud_model`
- Старое поле `current_model` помечено как DEPRECATED (но сохранено для обратной совместимости)

## Обратная совместимость
Миграция полностью обратно совместима:
1. Старое поле `current_model` сохраняется
2. При ошибке чтения новых полей используется fallback на старое поле
3. Существующие данные автоматически мигрируются в соответствующие поля

## После миграции
Бот автоматически:
1. Использует `current_local_model` когда AI_MODE=local
2. Использует `current_cloud_model` когда AI_MODE=openrouter
3. Сохраняет выбор пользователя в правильное поле при переключении модели

## Дефолтные значения
- `current_local_model`: `llama3-finance` (бесплатная локальная модель)
- `current_cloud_model`: `deepseek-chimera` (бесплатная облачная модель)
