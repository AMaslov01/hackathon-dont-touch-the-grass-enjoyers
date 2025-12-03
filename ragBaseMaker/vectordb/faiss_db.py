"""
FAISS vector database implementation.
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import json
import numpy as np

from ragBaseMaker.vectordb.base_vectordb import BaseVectorDB, SearchResult


class FAISSVectorDB(BaseVectorDB):
    """
    Vector database using FAISS.
    
    FAISS (Facebook AI Similarity Search) provides:
    - Very fast similarity search
    - GPU acceleration support
    - Efficient memory usage
    """
    
    def __init__(
        self,
        collection_name: str = 'documents',
        embedding_dimension: int = 768,
        persist_directory: Optional[str] = None,
        use_gpu: bool = False,
    ):
        """
        Initialize FAISS database.
        
        Args:
            collection_name: Name of the collection
            embedding_dimension: Dimension of embeddings
            persist_directory: Directory to persist data
            use_gpu: Whether to use GPU acceleration
        """
        super().__init__(collection_name, embedding_dimension)
        self.persist_directory = persist_directory
        self.use_gpu = use_gpu
        
        # Storage
        self._index = None
        self._id_to_idx: Dict[str, int] = {}
        self._idx_to_id: Dict[int, str] = {}
        self._texts: Dict[str, str] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self._next_idx = 0
        
        # Load if persist directory exists
        if persist_directory:
            self._load()
    
    def _init_index(self):
        """Initialize FAISS index."""
        if self._index is not None:
            return
        
        import faiss
        
        # Create index - using L2 distance (can be converted to cosine with normalization)
        self._index = faiss.IndexFlatIP(self.embedding_dimension)  # Inner product for normalized vectors
        
        if self.use_gpu:
            try:
                # Try to move to GPU
                res = faiss.StandardGpuResources()
                self._index = faiss.index_cpu_to_gpu(res, 0, self._index)
            except Exception:
                pass  # Fall back to CPU
    
    def add(
        self,
        ids: List[str],
        embeddings: np.ndarray,
        texts: List[str],
        metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        Add documents to FAISS.
        """
        self._init_index()
        
        # Normalize embeddings for cosine similarity
        embeddings = embeddings.astype(np.float32)
        faiss_module = __import__('faiss')
        faiss_module.normalize_L2(embeddings)
        
        # Add to index
        self._index.add(embeddings)
        
        # Store mappings
        for i, (doc_id, text) in enumerate(zip(ids, texts)):
            idx = self._next_idx + i
            self._id_to_idx[doc_id] = idx
            self._idx_to_id[idx] = doc_id
            self._texts[doc_id] = text
            
            if metadata and i < len(metadata):
                self._metadata[doc_id] = metadata[i]
            else:
                self._metadata[doc_id] = {}
        
        self._next_idx += len(ids)
        
        # Persist if needed
        if self.persist_directory:
            self._save()
    
    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """
        Search for similar documents in FAISS.
        """
        self._init_index()
        
        if self._index.ntotal == 0:
            return []
        
        # Normalize query
        query = query_embedding.astype(np.float32).reshape(1, -1)
        faiss_module = __import__('faiss')
        faiss_module.normalize_L2(query)
        
        # Search
        scores, indices = self._index.search(query, min(top_k * 2, self._index.ntotal))
        
        # Convert to results
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            
            doc_id = self._idx_to_id.get(idx)
            if doc_id is None:
                continue
            
            # Apply metadata filter if provided
            doc_metadata = self._metadata.get(doc_id, {})
            if filter_metadata:
                match = all(
                    doc_metadata.get(k) == v
                    for k, v in filter_metadata.items()
                )
                if not match:
                    continue
            
            results.append(SearchResult(
                id=doc_id,
                text=self._texts.get(doc_id, ''),
                score=float(score),
                metadata=doc_metadata,
            ))
            
            if len(results) >= top_k:
                break
        
        return results
    
    def delete(self, ids: List[str]) -> None:
        """
        Delete documents by ID.
        
        Note: FAISS doesn't support deletion well, so we mark as deleted
        and rebuild index periodically.
        """
        for doc_id in ids:
            if doc_id in self._id_to_idx:
                idx = self._id_to_idx[doc_id]
                del self._id_to_idx[doc_id]
                del self._idx_to_id[idx]
                del self._texts[doc_id]
                if doc_id in self._metadata:
                    del self._metadata[doc_id]
        
        # For now, we keep the vectors in the index
        # A full implementation would rebuild the index
        
        if self.persist_directory:
            self._save()
    
    def count(self) -> int:
        """Get document count."""
        return len(self._id_to_idx)
    
    def clear(self) -> None:
        """Clear all documents."""
        self._index = None
        self._id_to_idx = {}
        self._idx_to_id = {}
        self._texts = {}
        self._metadata = {}
        self._next_idx = 0
        
        self._init_index()
        
        if self.persist_directory:
            self._save()
    
    def _save(self) -> None:
        """Save index and metadata to disk."""
        if not self.persist_directory:
            return
        
        import faiss
        
        path = Path(self.persist_directory)
        path.mkdir(parents=True, exist_ok=True)
        
        # Save FAISS index
        index_path = path / f'{self.collection_name}.faiss'
        if hasattr(self._index, 'index'):
            # GPU index - copy to CPU first
            cpu_index = faiss.index_gpu_to_cpu(self._index)
            faiss.write_index(cpu_index, str(index_path))
        else:
            faiss.write_index(self._index, str(index_path))
        
        # Save metadata
        meta_path = path / f'{self.collection_name}.json'
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump({
                'id_to_idx': self._id_to_idx,
                'idx_to_id': {str(k): v for k, v in self._idx_to_id.items()},
                'texts': self._texts,
                'metadata': self._metadata,
                'next_idx': self._next_idx,
            }, f, ensure_ascii=False, indent=2)
    
    def _load(self) -> None:
        """Load index and metadata from disk."""
        if not self.persist_directory:
            return
        
        import faiss
        
        path = Path(self.persist_directory)
        index_path = path / f'{self.collection_name}.faiss'
        meta_path = path / f'{self.collection_name}.json'
        
        if not index_path.exists() or not meta_path.exists():
            return
        
        # Load FAISS index
        self._index = faiss.read_index(str(index_path))
        
        if self.use_gpu:
            try:
                res = faiss.StandardGpuResources()
                self._index = faiss.index_cpu_to_gpu(res, 0, self._index)
            except Exception:
                pass
        
        # Load metadata
        with open(meta_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self._id_to_idx = data['id_to_idx']
            self._idx_to_id = {int(k): v for k, v in data['idx_to_id'].items()}
            self._texts = data['texts']
            self._metadata = data['metadata']
            self._next_idx = data['next_idx']

