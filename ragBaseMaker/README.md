# RAG Base Maker

Простая и эффективная RAG (Retrieval-Augmented Generation) система для индексации и поиска по документам.

## 🚀 Быстрый старт

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Индексация документов

```bash
# Индексировать все документы из директории
python index_documents.py /path/to/your/documents

# Указать свою директорию для базы данных
python index_documents.py /path/to/documents --db ./my_rag_db
```

### 3. Использование в коде

```python
from rag_system import RAGSystem

# Создать RAG систему (загрузит существующую базу)
rag = RAGSystem(persist_directory='./rag_data')

# Поиск по документам
results = rag.search('ваш запрос', top_k=5)

for result in results:
    print(f"[{result.score:.3f}] {result.text[:200]}...")
    print(f"Источник: {result.metadata.get('source_title', 'Unknown')}\n")

# Получить контекст для LLM
context = rag.get_context('ваш запрос', top_k=3, max_tokens=2000)
print(context)
```

## 📚 Поддерживаемые форматы

- PDF (.pdf)
- Word документы (.docx)
- Excel таблицы (.xlsx, .xls)
- PowerPoint презентации (.pptx)
- HTML (.html, .htm)
- Markdown (.md)
- Текстовые файлы (.txt)

## 🎯 Особенности

- **Multilingual**: Поддержка русского и английского языков
- **E5 embeddings**: Использует state-of-the-art модель `intfloat/multilingual-e5-base`
- **Автоматический парсинг**: Определяет формат документа автоматически
- **Persistent storage**: Данные сохраняются на диске (ChromaDB или FAISS)
- **LangChain chunking**: Использует проверенный RecursiveCharacterTextSplitter с поддержкой overlap

## 🏗️ Структура проекта

```
ragBaseMaker/
├── rag_system.py              # Основная RAG система (полностью на LangChain!)
├── document_loader.py         # Загрузка документов (обертка над LangChain loaders)
├── requirements.txt           # Зависимости
│
└── embeddings/                # Модуль эмбеддингов
    └── multilingual_embedder.py  # Совместим с LangChain!
```

## ⚙️ Конфигурация

```python
rag = RAGSystem(
    persist_directory='./rag_data',              # Где хранить базу
    collection_name='documents',                 # Имя коллекции
    embedding_model='intfloat/multilingual-e5-base',  # Модель эмбеддингов
    chunk_size=512,                              # Размер чанка (для recursive)
    chunk_overlap=50,                            # Overlap между чанками
    chunker_type='recursive',                    # 'recursive' или 'semantic'
)
```

## 📝 Примеры использования

### Добавить один документ

```python
from rag_system import RAGSystem

rag = RAGSystem()
num_chunks = rag.add_document('path/to/document.pdf')
print(f"Добавлено {num_chunks} чанков")
```

### Поиск с фильтрацией

```python
# Искать только в определённых документах
results = rag.search(
    query='машинное обучение',
    top_k=5,
    filter_metadata={'source_title': 'Annual Report 2023'}
)
```

### Очистка базы

```python
rag.clear()  # Удалить все документы из базы
```

## 🔧 Требования

- Python 3.8+
- Зависимости из `requirements.txt`

## 📄 Лицензия

MIT License
