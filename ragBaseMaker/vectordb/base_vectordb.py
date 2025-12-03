"""
Base vector database class.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import numpy as np


@dataclass
class SearchResult:
    """Represents a search result from the vector database."""
    
    id: str  # Unique identifier
    text: str  # Original text
    score: float  # Similarity score (higher is better)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Optional embedding (if requested)
    embedding: Optional[np.ndarray] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'text': self.text,
            'score': self.score,
            'metadata': self.metadata,
        }


class BaseVectorDB(ABC):
    """
    Abstract base class for vector databases.
    """
    
    def __init__(
        self,
        collection_name: str = 'documents',
        embedding_dimension: int = 768,
    ):
        """
        Initialize the vector database.
        
        Args:
            collection_name: Name of the collection
            embedding_dimension: Dimension of embeddings
        """
        self.collection_name = collection_name
        self.embedding_dimension = embedding_dimension
    
    @abstractmethod
    def add(
        self,
        ids: List[str],
        embeddings: np.ndarray,
        texts: List[str],
        metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        Add documents to the database.
        
        Args:
            ids: Unique identifiers for each document
            embeddings: Embedding vectors (shape: [n, dimension])
            texts: Original text content
            metadata: Optional metadata for each document
        """
        pass
    
    @abstractmethod
    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """
        Search for similar documents.
        
        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            filter_metadata: Optional metadata filter
            
        Returns:
            List of SearchResult objects
        """
        pass
    
    @abstractmethod
    def delete(self, ids: List[str]) -> None:
        """
        Delete documents by ID.
        
        Args:
            ids: List of document IDs to delete
        """
        pass
    
    @abstractmethod
    def count(self) -> int:
        """
        Get the number of documents in the database.
        
        Returns:
            Document count
        """
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """
        Clear all documents from the database.
        """
        pass
    
    def add_single(
        self,
        id: str,
        embedding: np.ndarray,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add a single document.
        
        Args:
            id: Document ID
            embedding: Embedding vector
            text: Original text
            metadata: Optional metadata
        """
        self.add(
            ids=[id],
            embeddings=np.array([embedding]),
            texts=[text],
            metadata=[metadata] if metadata else None,
        )

