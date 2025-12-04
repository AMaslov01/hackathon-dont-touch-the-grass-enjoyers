#!/usr/bin/env python3
"""
RAG database management utility.
View stats, clear database, etc.

Usage:
    python rag_tools/manage_rag.py stats
    python rag_tools/manage_rag.py clear
    python rag_tools/manage_rag.py test
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from ragBaseMaker.rag_system import RAGSystem
    RAG_AVAILABLE = True
except ImportError as e:
    print(f"❌ Ошибка: не удалось импортировать RAG систему")
    print(f"   Запустите: python copy_ragbasemaker.py")
    print(f"   Ошибка: {e}")
    RAG_AVAILABLE = False
    RAGSystem = None


def get_rag_instance():
    """Get RAG instance for management tools."""
    if not RAG_AVAILABLE:
        return None
    
    rag_data_dir = Path(__file__).parent.parent / 'rag_data'
    
    try:
        return RAGSystem(
            persist_directory=str(rag_data_dir),
            collection_name='financial_docs',
            embedding_model='intfloat/multilingual-e5-base',
            chunk_size=512,
            chunk_overlap=50,
        )
    except Exception as e:
        print(f"❌ Ошибка инициализации RAG: {e}")
        return None


def is_rag_available():
    """Check if RAG is available and has documents."""
    if not RAG_AVAILABLE:
        return False
    
    rag = get_rag_instance()
    if not rag:
        return False
    
    try:
        return rag.count_documents() > 0
    except:
        return False


def show_stats():
    """Show RAG database statistics."""
    print("=" * 70)
    print("  RAG DATABASE STATISTICS")
    print("=" * 70)
    
    if not RAG_AVAILABLE:
        print("\n❌ RAG система недоступна")
        print("   Убедитесь, что ragBaseMaker находится в родительской директории")
        return
    
    try:
        rag = get_rag_instance()
        if not rag:
            print("\n❌ Не удалось инициализировать RAG систему")
            return
        
        stats = rag.get_stats()
        
        print(f"\n📊 Status:             {'✅ Available' if stats.get('available') else '❌ Not available'}")
        print(f"📦 Total chunks:       {stats.get('total_chunks', 0)}")
        print(f"💾 Database location:  {stats.get('persist_directory', 'Unknown')}")
        print(f"📚 Collection name:    {stats.get('collection_name', 'Unknown')}")
        print(f"🤖 Embedding model:    {stats.get('embedding_model', 'Unknown')}")
        
        if 'error' in stats:
            print(f"\n⚠️  Error: {stats['error']}")
        
        print("\n" + "=" * 70)
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")


def clear_database():
    """Clear all documents from RAG database."""
    print("=" * 70)
    print("  CLEAR RAG DATABASE")
    print("=" * 70)
    
    # Confirmation
    print("\n⚠️  ВНИМАНИЕ: Это удалит все документы из базы данных!")
    response = input("   Вы уверены? (yes/no): ")
    
    if response.lower() not in ['yes', 'y', 'да']:
        print("\n✅ Операция отменена")
        return
    
    try:
        rag = get_rag_instance()
        if not rag:
            print("\n❌ Не удалось инициализировать RAG систему")
            return
        
        # Get count before clearing
        count_before = rag.count_documents()
        
        print(f"\n🗑️  Удаляю {count_before} чанков...")
        rag.clear()
        
        count_after = rag.count_documents()
        print(f"✅ База данных очищена ({count_before} → {count_after})")
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")


def test_rag():
    """Test RAG system with sample queries."""
    print("=" * 70)
    print("  TEST RAG SYSTEM")
    print("=" * 70)
    
    if not is_rag_available():
        print("\n❌ RAG система недоступна или база пуста")
        print("\nДобавьте документы:")
        print("  python rag_tools/add_documents.py /path/to/documents")
        return
    
    try:
        rag = get_rag_instance()
        if not rag:
            print("\n❌ Не удалось инициализировать RAG систему")
            return
        
        # Test queries
        test_queries = [
            "финансовый план",
            "увеличение прибыли",
            "управление рисками",
        ]
        
        print("\n🧪 Тестовые запросы:\n")
        
        for query in test_queries:
            print(f"\n📝 Запрос: '{query}'")
            results = rag.search(query, top_k=2)
            
            if results:
                print(f"   ✅ Найдено {len(results)} результатов")
                for i, result in enumerate(results, 1):
                    score = result['score']
                    text = result['text'][:100]
                    print(f"      [{i}] Score: {score:.4f} | {text}...")
            else:
                print("   ❌ Ничего не найдено")
        
        print("\n✅ Тест завершен")
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")


def main():
    if len(sys.argv) < 2:
        print("RAG Database Management Tool")
        print("\nUsage:")
        print(f"  python {sys.argv[0]} stats  - Show database statistics")
        print(f"  python {sys.argv[0]} clear  - Clear all documents")
        print(f"  python {sys.argv[0]} test   - Test RAG system")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == 'stats':
        show_stats()
    elif command == 'clear':
        clear_database()
    elif command == 'test':
        test_rag()
    else:
        print(f"❌ Unknown command: {command}")
        print("   Available: stats, clear, test")
        sys.exit(1)


if __name__ == '__main__':
    main()

