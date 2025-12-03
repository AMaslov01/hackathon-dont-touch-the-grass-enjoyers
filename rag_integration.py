"""
Simple wrapper for ragBaseMaker RAG system.
Provides convenient interface for the bot.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from ragBaseMaker.rag_system import RAGSystem
    RAG_AVAILABLE = True
except ImportError as e:
    logger.warning(f"RAG not available: {e}. Run: python copy_ragbasemaker.py")
    RAG_AVAILABLE = False
    RAGSystem = None

# Global RAG instance
_rag_instance: Optional['RAGSystem'] = None


def get_rag(persist_directory: str = './rag_data') -> Optional['RAGSystem']:
    """Get or create RAG system instance."""
    global _rag_instance
    
    if not RAG_AVAILABLE:
        return None
    
    if _rag_instance is None:
        try:
            _rag_instance = RAGSystem(
                persist_directory=persist_directory,
                collection_name='financial_docs',
                embedding_model='intfloat/multilingual-e5-base',
                chunk_size=512,
                chunk_overlap=50,
            )
            logger.info(f"RAG initialized: {_rag_instance.count_documents()} chunks")
        except Exception as e:
            logger.error(f"RAG init failed: {e}")
            return None
    
    return _rag_instance


def is_rag_available() -> bool:
    """Check if RAG is available and has documents."""
    rag = get_rag()
    return rag is not None and rag.count_documents() > 0

