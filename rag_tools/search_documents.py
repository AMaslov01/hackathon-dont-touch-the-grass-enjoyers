#!/usr/bin/env python3
"""
Utility to search documents in RAG database.
Useful for testing and debugging.

Usage:
    python rag_tools/search_documents.py "your query"
    python rag_tools/search_documents.py "финансовый план" --top-k 10
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_integration import get_bot_rag, is_rag_available


def main():
    print("=" * 70)
    print("  ПОИСК В RAG БАЗЕ")
    print("=" * 70)
    
    # Parse arguments
    if len(sys.argv) < 2:
        print("\n❌ Ошибка: укажите поисковый запрос")
        print("\nИспользование:")
        print(f"  python {sys.argv[0]} 'your query'")
        print(f"  python {sys.argv[0]} 'финансовый план' --top-k 10")
        print("\nПримеры:")
        print(f"  python {sys.argv[0]} 'как увеличить прибыль'")
        print(f"  python {sys.argv[0]} 'финансовый анализ' --top-k 5")
        sys.exit(1)
    
    query = sys.argv[1]
    
    # Parse top-k
    top_k = 5
    if '--top-k' in sys.argv:
        try:
            idx = sys.argv.index('--top-k')
            top_k = int(sys.argv[idx + 1])
        except (IndexError, ValueError):
            print("⚠️  Неверное значение --top-k, использую 5")
    
    print(f"\n🔍 Запрос: {query}")
    print(f"📊 Топ-K:  {top_k}")
    print()
    
    # Check RAG availability
    if not is_rag_available():
        print("❌ RAG система недоступна или база пуста")
        print("\nДобавьте документы:")
        print("  python rag_tools/add_documents.py /path/to/documents")
        sys.exit(1)
    
    # Get RAG system
    try:
        rag = get_bot_rag()
        if not rag:
            print("❌ Не удалось инициализировать RAG систему")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)
    
    # Show stats
    stats = rag.get_stats()
    print(f"💾 Документов в базе: {stats.get('total_chunks', 0)} чанков")
    print(f"🤖 Модель эмбеддингов: {stats.get('embedding_model', 'Unknown')}")
    print()
    
    # Search
    print("🔍 Выполняю поиск...\n")
    
    try:
        results = rag.search(query, top_k=top_k)
        
        if not results:
            print("❌ Ничего не найдено")
            sys.exit(0)
        
        print(f"✅ Найдено {len(results)} результатов:\n")
        print("=" * 70)
        
        for i, result in enumerate(results, 1):
            score = result['score']
            text = result['text']
            metadata = result['metadata']
            
            source_title = metadata.get('source_title', 'Unknown')
            source_path = metadata.get('source_path', 'Unknown')
            
            print(f"\n[{i}] Score: {score:.4f}")
            print(f"    Source: {source_title}")
            print(f"    File: {Path(source_path).name}")
            print(f"\n    {text[:300]}...")
            if len(text) > 300:
                print(f"    ... (+{len(text) - 300} chars)")
        
        print("\n" + "=" * 70)
        
        # Show context
        print("\n📝 Контекст для LLM:\n")
        context = rag.get_context(query, top_k=min(3, top_k), max_tokens=2000)
        print(context[:500] + "..." if len(context) > 500 else context)
        if len(context) > 500:
            print(f"\n... (+{len(context) - 500} chars)")
        
    except Exception as e:
        print(f"❌ Ошибка поиска: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

