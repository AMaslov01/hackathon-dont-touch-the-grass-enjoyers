"""
Vector database module for RAG system.
Supports ChromaDB and FAISS backends.
"""

from ragBaseMaker.vectordb.base_vectordb import BaseVectorDB, SearchResult
from ragBaseMaker.vectordb.chroma_db import ChromaVectorDB
from ragBaseMaker.vectordb.faiss_db import FAISSVectorDB

__all__ = [
    'BaseVectorDB',
    'SearchResult',
    'ChromaVectorDB',
    'FAISSVectorDB',
]
