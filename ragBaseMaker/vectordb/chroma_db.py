"""
ChromaDB vector database implementation.
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import numpy as np

from ragBaseMaker.vectordb.base_vectordb import BaseVectorDB, SearchResult


class ChromaVectorDB(BaseVectorDB):
    """
    Vector database using ChromaDB.
    
    ChromaDB is an open-source embedding database that provides:
    - Persistent storage
    - Metadata filtering
    - Easy to use API
    """
    
    def __init__(
        self,
        collection_name: str = 'documents',
        embedding_dimension: int = 768,
        persist_directory: Optional[str] = None,
    ):
        """
        Initialize ChromaDB.
        
        Args:
            collection_name: Name of the collection
            embedding_dimension: Dimension of embeddings
            persist_directory: Directory to persist data (None for in-memory)
        """
        super().__init__(collection_name, embedding_dimension)
        self.persist_directory = persist_directory
        
        self._client = None
        self._collection = None
    
    def _init_client(self):
        """Initialize ChromaDB client lazily."""
        if self._client is not None:
            return
        
        import chromadb
        from chromadb.config import Settings
        
        if self.persist_directory:
            # Create directory if needed
            Path(self.persist_directory).mkdir(parents=True, exist_ok=True)
            
            self._client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(anonymized_telemetry=False),
            )
        else:
            self._client = chromadb.Client(
                settings=Settings(anonymized_telemetry=False),
            )
        
        # Get or create collection
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={'dimension': self.embedding_dimension},
        )
    
    @property
    def collection(self):
        """Get the ChromaDB collection."""
        self._init_client()
        return self._collection
    
    def add(
        self,
        ids: List[str],
        embeddings: np.ndarray,
        texts: List[str],
        metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        Add documents to ChromaDB.
        """
        self._init_client()
        
        # Prepare metadata (ChromaDB requires all values to be strings, ints, or floats)
        if metadata:
            cleaned_metadata = []
            for m in metadata:
                cleaned = {}
                for k, v in m.items():
                    if isinstance(v, (str, int, float, bool)):
                        cleaned[k] = v
                    else:
                        cleaned[k] = str(v)
                cleaned_metadata.append(cleaned)
        else:
            cleaned_metadata = None
        
        self._collection.add(
            ids=ids,
            embeddings=embeddings.tolist(),
            documents=texts,
            metadatas=cleaned_metadata,
        )
    
    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """
        Search for similar documents in ChromaDB.
        """
        self._init_client()
        
        # Prepare query
        query_kwargs = {
            'query_embeddings': [query_embedding.tolist()],
            'n_results': top_k,
            'include': ['documents', 'metadatas', 'distances'],
        }
        
        if filter_metadata:
            query_kwargs['where'] = filter_metadata
        
        results = self._collection.query(**query_kwargs)
        
        # Convert to SearchResult objects
        search_results = []
        
        if results['ids'] and results['ids'][0]:
            for i in range(len(results['ids'][0])):
                # ChromaDB returns L2 distance, convert to similarity
                # Lower distance = higher similarity
                distance = results['distances'][0][i] if results['distances'] else 0
                similarity = 1.0 / (1.0 + distance)  # Convert to 0-1 range
                
                search_results.append(SearchResult(
                    id=results['ids'][0][i],
                    text=results['documents'][0][i] if results['documents'] else '',
                    score=similarity,
                    metadata=results['metadatas'][0][i] if results['metadatas'] else {},
                ))
        
        return search_results
    
    def delete(self, ids: List[str]) -> None:
        """Delete documents by ID."""
        self._init_client()
        self._collection.delete(ids=ids)
    
    def count(self) -> int:
        """Get document count."""
        self._init_client()
        return self._collection.count()
    
    def clear(self) -> None:
        """Clear all documents."""
        self._init_client()
        
        # Delete and recreate collection
        self._client.delete_collection(self.collection_name)
        self._collection = self._client.create_collection(
            name=self.collection_name,
            metadata={'dimension': self.embedding_dimension},
        )
    
    def get_by_ids(self, ids: List[str]) -> List[Dict[str, Any]]:
        """
        Get documents by their IDs.
        
        Args:
            ids: List of document IDs
            
        Returns:
            List of document dictionaries
        """
        self._init_client()
        
        results = self._collection.get(
            ids=ids,
            include=['documents', 'metadatas', 'embeddings'],
        )
        
        documents = []
        for i in range(len(results['ids'])):
            documents.append({
                'id': results['ids'][i],
                'text': results['documents'][i] if results['documents'] else '',
                'metadata': results['metadatas'][i] if results['metadatas'] else {},
                'embedding': results['embeddings'][i] if results['embeddings'] else None,
            })
        
        return documents

