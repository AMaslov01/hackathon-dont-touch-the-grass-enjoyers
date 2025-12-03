#!/bin/bash
# Загрузка документов в RAG базу

if [ $# -eq 0 ]; then
    echo "Использование: ./load_documents.sh <путь>"
    echo ""
    echo "Примеры:"
    echo "  ./load_documents.sh test_documents"
    echo "  ./load_documents.sh /path/to/docs"
    echo "  ./load_documents.sh document.pdf"
    exit 1
fi

python rag_tools/add_documents.py "$1" --recursive
