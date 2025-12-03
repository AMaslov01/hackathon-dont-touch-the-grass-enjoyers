"""
Vector database module for RAG system.
Supports ChromaDB and FAISS backends.
"""

from .base_vectordb import BaseVectorDB, SearchResult
from .chroma_db import ChromaVectorDB
from .faiss_db import FAISSVectorDB

__all__ = [
    'BaseVectorDB',
    'SearchResult',
    'ChromaVectorDB',
    'FAISSVectorDB',
]
