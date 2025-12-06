# 🎉 Переход на упрощённый PDF генератор

## Что изменилось?

Старый `pdf_generator.py` (968 строк с ReportLab) заменён на `pdf_generator_simple.py` (~250 строк с WeasyPrint).

### ✅ Преимущества:

- **~70% меньше кода** (968 → 250 строк)
- **Автоматическая поддержка UTF-8/Cyrillic** (не нужно вручную качать шрифты)
- **CSS стилизация** из коробки
- **Автоматический парсинг Markdown** (таблицы, списки, заголовки)
- **Проще поддерживать и расширять**

## 📦 Установка зависимостей

### Ubuntu/Debian (WSL):
```bash
# Системные зависимости для WeasyPrint
sudo apt-get update
sudo apt-get install -y \
    python3-pip \
    python3-cffi \
    python3-brotli \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libffi-dev \
    libjpeg-dev \
    libopenjp2-7 \
    libxml2 \
    libxslt1.1

# Python пакеты
pip install weasyprint markdown
```

### Windows (native):
```bash
# Скачайте GTK3 runtime: https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases
# Затем установите Python пакеты:
pip install weasyprint markdown
```

### macOS:
```bash
brew install pango
pip install weasyprint markdown
```

### Docker (если используется):
```dockerfile
RUN apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    && pip install weasyprint markdown
```

## 🔧 Что делать, если WeasyPrint не устанавливается?

### Вариант 1: Использовать pdfkit (проще установить)
```bash
# Ubuntu/WSL
sudo apt-get install wkhtmltopdf
pip install pdfkit markdown

# Windows
# Скачайте wkhtmltopdf: https://wkhtmltopdf.org/downloads.html
pip install pdfkit markdown
```

### Вариант 2: Вернуться к старому генератору
```python
# В bot.py замените:
from pdf_generator_simple import pdf_generator, chat_history_pdf
# На:
from pdf_generator import pdf_generator, chat_history_pdf
```

## 🧪 Проверка работы

```python
# Запустите в Python:
from pdf_generator_simple import pdf_generator, WEASYPRINT_AVAILABLE

if WEASYPRINT_AVAILABLE:
    print("✅ WeasyPrint установлен и готов к работе!")
else:
    print("❌ WeasyPrint не установлен. Установите зависимости.")
```

## 📝 Изменения в коде

Интерфейс остался **полностью совместимым**:

```python
# Финансовый план
pdf_path = pdf_generator.generate(
    ai_response=financial_plan,
    business_info=business_info,
    user_name=user_name
)

# История чата
pdf_path = chat_history_pdf.generate(
    chat_history=chat_history,
    user_name=user_name
)
```

## 🐛 Troubleshooting

### Ошибка: "ImportError: WeasyPrint not installed"
**Решение:** Установите зависимости (см. выше)

### Ошибка: "cairo library not found"
**Решение (Ubuntu):**
```bash
sudo apt-get install libcairo2 libcairo2-dev
```

### Ошибка: "Pango not found"
**Решение (Ubuntu):**
```bash
sudo apt-get install libpango-1.0-0 libpangocairo-1.0-0
```

### PDF генерируется, но кириллица отображается как квадратики
**Решение:** Установите шрифты:
```bash
sudo apt-get install fonts-dejavu-core fonts-liberation
```

## 📊 Сравнение версий

| Параметр | Старый (ReportLab) | Новый (WeasyPrint) |
|----------|-------------------|-------------------|
| Строк кода | 968 | ~250 |
| UTF-8/Cyrillic | Вручную | ✅ Автоматически |
| Markdown | Вручную парсим | ✅ Библиотека |
| CSS | Нет | ✅ Да |
| Таблицы | Вручную | ✅ Автоматически |
| Зависимости | reportlab | weasyprint + markdown |

## 🔄 Rollback (если что-то пошло не так)

```bash
# 1. Верните старый импорт в bot.py
# 2. Удалите новый генератор (опционально)
rm pdf_generator_simple.py
```

## ✨ Дополнительные возможности

Теперь можно легко настраивать стили через CSS в `pdf_generator_simple.py`:
- Изменить цвета
- Добавить логотипы
- Настроить шрифты
- Добавить колонтитулы
- И многое другое!

## 📚 Полезные ссылки

- [WeasyPrint Documentation](https://weasyprint.readthedocs.io/)
- [Python Markdown](https://python-markdown.github.io/)
- [CSS for Print](https://www.smashingmagazine.com/2015/01/designing-for-print-with-css/)
