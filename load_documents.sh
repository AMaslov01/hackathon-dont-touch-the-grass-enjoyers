#!/bin/bash
# Загрузка документов в RAG базу

if [ $# -eq 0 ]; then
    echo "Использование: ./load_documents.sh <путь> [флаги]"
    echo ""
    echo "Примеры:"
    echo "  ./load_documents.sh test_documents                    # Загрузить папку"
    echo "  ./load_documents.sh test_documents/file.pdf           # Загрузить файл"
    echo "  ./load_documents.sh test_documents --semantic         # С семантическим чанкингом"
    echo "  ./load_documents.sh /path/to/docs                     # Загрузить свою папку"
    echo ""
    echo "Флаги:"
    echo "  --semantic, -s    Семантический чанкинг (качественнее, медленнее)"
    exit 1
fi

TARGET="$1"
shift  # Убираем первый аргумент, оставляем остальные флаги

# Проверяем существует ли путь
if [ ! -e "$TARGET" ]; then
    echo "❌ Ошибка: '$TARGET' не найден"
    exit 1
fi

# Если это директория - добавляем --recursive
if [ -d "$TARGET" ]; then
    echo "📁 Загрузка папки: $TARGET (рекурсивно)"
    python3 rag_tools/add_documents.py "$TARGET" --recursive "$@"
# Если это файл - загружаем без --recursive
elif [ -f "$TARGET" ]; then
    echo "📄 Загрузка файла: $TARGET"
    python3 rag_tools/add_documents.py "$TARGET" "$@"
else
    echo "❌ Ошибка: '$TARGET' не является файлом или папкой"
    exit 1
fi
