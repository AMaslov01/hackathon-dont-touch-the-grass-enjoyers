# 🚀 Установка WeasyPrint для улучшенной генерации PDF

## ⚡ Быстрая установка (Ubuntu/Debian/WSL)

```bash
# Установите системные библиотеки
sudo apt-get update
sudo apt-get install -y \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    libcairo2 \
    shared-mime-info

# Python пакеты уже установлены через requirements.txt
# Если нет, запустите:
pip install weasyprint markdown
```

## 🔄 После установки

Перезапустите бот:
```bash
python bot.py
```

Должно появиться сообщение:
```
✅ WeasyPrint loaded successfully
```

## 💡 Текущий статус

**Бот работает с fallback на ReportLab!** 

Даже без WeasyPrint бот полностью функционален, используя старый PDF генератор.

Установка WeasyPrint даст вам:
- ✅ На 70% меньше кода (~250 строк вместо 968)
- ✅ Лучшую поддержку Markdown
- ✅ CSS стилизацию
- ✅ Автоматическую обработку таблиц

## 🐛 Решение проблем

### Ошибка: "cannot load library 'libpango-1.0-0'"
**Решение:** Запустите команды выше для установки системных библиотек

### Ошибка: "No module named 'weasyprint'"
**Решение:** 
```bash
pip install weasyprint markdown
```

### Ошибка: "cairo library not found"
**Решение:**
```bash
sudo apt-get install libcairo2 libcairo2-dev
```

### Бот работает, но используется ReportLab
Это нормально! Fallback работает автоматически. Установите WeasyPrint для улучшенной функциональности.

## ✅ Проверка установки

```bash
python3 -c "from pdf_generator_simple import WEASYPRINT_AVAILABLE, REPORTLAB_FALLBACK; \
print('✅ WeasyPrint:', WEASYPRINT_AVAILABLE); \
print('✅ ReportLab fallback:', REPORTLAB_FALLBACK)"
```

Ожидаемый результат после установки:
```
✅ WeasyPrint: True
✅ ReportLab fallback: False
```

Текущий результат (без установки):
```
✅ WeasyPrint: False
✅ ReportLab fallback: True
```

## 📚 Дополнительные ресурсы

- [WeasyPrint Installation Guide](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html)
- [Troubleshooting](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#troubleshooting)
