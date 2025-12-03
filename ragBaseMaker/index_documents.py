#!/usr/bin/env python3
"""
Простой скрипт для индексации документов в RAG систему.

Использование:
    python index_documents.py /path/to/documents
    python index_documents.py /path/to/documents --db ./my_rag_db
"""

import sys
from pathlib import Path
from rag_system import RAGSystem


def main():
    # Проверка аргументов
    if len(sys.argv) < 2:
        print("❌ Ошибка: укажите путь к директории с документами")
        print("\nИспользование:")
        print(f"  python {sys.argv[0]} /path/to/documents")
        print(f"  python {sys.argv[0]} /path/to/documents --db ./my_rag_db")
        sys.exit(1)
    
    # Путь к документам
    docs_path = Path(sys.argv[1])
    
    # Путь к базе данных (опционально)
    db_path = './rag_data'
    if len(sys.argv) > 2 and sys.argv[2] == '--db' and len(sys.argv) > 3:
        db_path = sys.argv[3]
    
    # Проверка существования директории
    if not docs_path.exists():
        print(f"❌ Ошибка: директория '{docs_path}' не существует")
        sys.exit(1)
    
    if not docs_path.is_dir():
        print(f"❌ Ошибка: '{docs_path}' не является директорией")
        sys.exit(1)
    
    print("="*70)
    print("  RAG СИСТЕМА - ИНДЕКСАЦИЯ ДОКУМЕНТОВ")
    print("="*70)
    print(f"\n📁 Директория с документами: {docs_path.absolute()}")
    print(f"💾 База данных RAG:          {Path(db_path).absolute()}")
    print()
    
    # Создание RAG системы
    print("⚙️  Инициализация RAG системы...")
    rag = RAGSystem(
        persist_directory=db_path,
        embedding_model='intfloat/multilingual-e5-base',
        chunk_size=512,
        chunk_overlap=50,
    )
    
    # Подсчёт существующих документов
    existing_count = rag.count_documents()
    if existing_count > 0:
        print(f"📊 В базе уже есть {existing_count} чанков")
    
    # Индексация документов
    print(f"\n📥 Начинаю индексацию документов из '{docs_path}'...\n")
    
    try:
        results = rag.add_directory(
            directory=str(docs_path),
            recursive=True,
            extensions=None,  # Все поддерживаемые форматы
        )
        
        # Статистика
        print("\n" + "="*70)
        print("  РЕЗУЛЬТАТЫ")
        print("="*70)
        
        successful = sum(1 for v in results.values() if isinstance(v, int))
        failed = len(results) - successful
        total_chunks = sum(v for v in results.values() if isinstance(v, int))
        
        print(f"\n✅ Успешно обработано: {successful} файлов")
        print(f"❌ Ошибок:             {failed} файлов")
        print(f"📦 Всего чанков:       {total_chunks}")
        print(f"💾 Чанков в базе:      {rag.count_documents()}")
        
        if failed > 0:
            print("\n⚠️  Файлы с ошибками:")
            for path, result in results.items():
                if not isinstance(result, int):
                    print(f"  - {path}: {result}")
        
        print("\n✨ Индексация завершена!")
        print(f"\nТеперь можно использовать базу для поиска:")
        print(f"  from rag_system import RAGSystem")
        print(f"  rag = RAGSystem(persist_directory='{db_path}')")
        print(f"  results = rag.search('ваш запрос')")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Индексация прервана пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Ошибка при индексации: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

