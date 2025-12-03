#!/usr/bin/env python3
"""
Utility to add documents to RAG database.
Uses ragBaseMaker system to index documents.

Usage:
    python rag_tools/add_documents.py /path/to/documents
    python rag_tools/add_documents.py document.pdf
    python rag_tools/add_documents.py /path/to/documents --recursive
"""

import sys
import os
from pathlib import Path

# Add parent directory to path to import from bot project
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from ragBaseMaker.rag_system import RAGSystem
except ImportError as e:
    print(f"❌ Ошибка: не удалось импортировать RAG систему")
    print(f"   Запустите: python copy_ragbasemaker.py")
    print(f"   Ошибка: {e}")
    sys.exit(1)


def main():
    print("=" * 70)
    print("  ДОБАВЛЕНИЕ ДОКУМЕНТОВ В RAG БАЗУ")
    print("=" * 70)
    
    # Parse arguments
    if len(sys.argv) < 2:
        print("\n❌ Ошибка: укажите путь к документу или директории")
        print("\nИспользование:")
        print(f"  python {sys.argv[0]} /path/to/documents")
        print(f"  python {sys.argv[0]} document.pdf")
        print(f"  python {sys.argv[0]} /path/to/documents --recursive")
        print("\nПримеры:")
        print(f"  python {sys.argv[0]} ./financial_reports")
        print(f"  python {sys.argv[0]} ./annual_report_2023.pdf")
        sys.exit(1)
    
    target_path = Path(sys.argv[1])
    recursive = '--recursive' in sys.argv or '-r' in sys.argv
    
    # Check if path exists
    if not target_path.exists():
        print(f"\n❌ Ошибка: путь '{target_path}' не существует")
        sys.exit(1)
    
    # RAG configuration
    rag_data_dir = Path(__file__).parent.parent / 'rag_data'
    
    print(f"\n📁 Источник:         {target_path.absolute()}")
    print(f"💾 База RAG:         {rag_data_dir.absolute()}")
    print(f"🔄 Рекурсивно:       {'Да' if recursive else 'Нет'}")
    print()
    
    # Initialize RAG system
    print("⚙️  Инициализация RAG системы...")
    try:
        rag = RAGSystem(
            persist_directory=str(rag_data_dir),
            collection_name='financial_docs',
            embedding_model='intfloat/multilingual-e5-base',
            chunk_size=512,
            chunk_overlap=50,
        )
    except Exception as e:
        print(f"❌ Ошибка инициализации RAG: {e}")
        sys.exit(1)
    
    # Show current stats
    existing_count = rag.count_documents()
    if existing_count > 0:
        print(f"📊 В базе уже есть {existing_count} чанков")
    
    print()
    
    # Add documents
    try:
        if target_path.is_file():
            # Single file
            print(f"📄 Добавляю файл: {target_path.name}")
            count = rag.add_document(str(target_path))
            print(f"✅ Добавлено {count} чанков из {target_path.name}")
            results = {str(target_path): count}
        
        elif target_path.is_dir():
            # Directory
            print(f"📁 Индексирую директорию: {target_path.name}")
            if recursive:
                print("   (включая поддиректории)")
            print()
            
            results = rag.add_directory(
                directory=str(target_path),
                recursive=recursive,
                extensions=None,  # All supported formats
            )
        
        else:
            print(f"❌ Ошибка: '{target_path}' не является файлом или директорией")
            sys.exit(1)
        
        # Statistics
        print("\n" + "=" * 70)
        print("  РЕЗУЛЬТАТЫ")
        print("=" * 70)
        
        successful = sum(1 for v in results.values() if isinstance(v, int))
        failed = len(results) - successful
        total_chunks = sum(v for v in results.values() if isinstance(v, int))
        
        print(f"\n✅ Успешно обработано: {successful} файлов")
        print(f"❌ Ошибок:             {failed} файлов")
        print(f"📦 Добавлено чанков:   {total_chunks}")
        print(f"💾 Всего в базе:       {rag.count_documents()}")
        
        if failed > 0:
            print("\n⚠️  Файлы с ошибками:")
            for path, result in results.items():
                if not isinstance(result, int):
                    print(f"  - {Path(path).name}: {result}")
        
        print("\n✨ Индексация завершена!")
        print("\nТеперь бот может использовать эти документы для ответов.")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Индексация прервана пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

