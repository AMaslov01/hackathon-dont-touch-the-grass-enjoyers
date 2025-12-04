"""
Multilingual embedder using Sentence Transformers.
Optimized for Russian + English RAG applications.
Compatible with LangChain Embeddings interface.
"""

from typing import List, Union, Optional, Tuple
import numpy as np

try:
    from langchain.embeddings.base import Embeddings
    LANGCHAIN_AVAILABLE = True
except ImportError:
    # Fallback if LangChain not installed
    LANGCHAIN_AVAILABLE = False
    class Embeddings:  # type: ignore
        """Dummy base class when LangChain not available."""
        pass


class MultilingualEmbedder(Embeddings):
    """
    Multilingual embedding model using Sentence Transformers.
    
    Recommended for Russian + English RAG systems.
    Supports E5 models with query/passage prefixes.
    """
    
    def __init__(
        self,
        model_name: str = 'intfloat/multilingual-e5-base',
        device: Optional[str] = None,
        use_query_prefix: bool = True,
    ):
        """
        Initialize the multilingual embedder.
        
        Args:
            model_name: HuggingFace model name
            device: Device to use ('cuda', 'cpu', or None for auto)
            use_query_prefix: Whether to use E5-style prefixes (query:/passage:)
        """
        self.model_name = model_name
        self.device = device
        self.use_query_prefix = use_query_prefix
        self._dimension: Optional[int] = None
        
        # Check if this is an E5 model (needs prefixes)
        self._is_e5_model = 'e5' in model_name.lower()
        
        # Lazy load the model
        self._model = None
    
    def _load_model(self):
        """Load the model lazily."""
        if self._model is not None:
            return
        
        from sentence_transformers import SentenceTransformer
        
        self._model = SentenceTransformer(
            self.model_name,
            device=self.device,
        )
    
        
        # Get dimension from model
        self._dimension = self._model.get_sentence_embedding_dimension()
    
    @property
    def dimension(self) -> int:
        """Get the embedding dimension."""
        if self._dimension is None:
            self._load_model()
        return self._dimension or 768  # Default fallback
    
    def _prepare_texts(
        self,
        texts: List[str],
        is_query: bool = False,
    ) -> List[str]:
        """
        Prepare texts for embedding (add prefixes for E5 models).
        
        Args:
            texts: List of texts
            is_query: Whether these are queries (vs documents)
            
        Returns:
            Prepared texts with prefixes if needed
        """
        if not self._is_e5_model or not self.use_query_prefix:
            return texts
        
        prefix = 'query: ' if is_query else 'passage: '
        return [prefix + text for text in texts]
    
    def encode(
        self,
        texts: Union[str, List[str]],
        batch_size: int = 32,
        show_progress: bool = False,
        is_query: bool = False,
    ) -> np.ndarray:
        """
        Encode texts into embeddings.
        
        Args:
            texts: Single text or list of texts
            batch_size: Batch size for processing
            show_progress: Show progress bar
            is_query: Whether these are queries (affects E5 prefix)
            
        Returns:
            NumPy array of embeddings (shape: [n_texts, dimension])
        """
        self._load_model()
        
        # Handle single text
        if isinstance(texts, str):
            texts = [texts]
        
        # Prepare texts (add prefixes if needed)
        prepared_texts = self._prepare_texts(texts, is_query)
        
        # Encode
        embeddings = self._model.encode(
            prepared_texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
            normalize_embeddings=True,  # L2 normalize for cosine similarity
        )
        
        return embeddings
    
    def encode_query(self, query: str) -> np.ndarray:
        """
        Encode a search query.
        Uses 'query:' prefix for E5 models.
        
        Args:
            query: Search query text
            
        Returns:
            Query embedding (1D array)
        """
        return self.encode([query], is_query=True)[0]
    
    def encode_documents(
        self,
        documents: List[str],
        batch_size: int = 32,
        show_progress: bool = False,
    ) -> np.ndarray:
        """
        Encode documents for indexing.
        Uses 'passage:' prefix for E5 models.
        
        Args:
            documents: List of document texts
            batch_size: Batch size
            show_progress: Show progress bar
            
        Returns:
            Document embeddings (2D array)
        """
        return self.encode(
            documents,
            batch_size=batch_size,
            show_progress=show_progress,
            is_query=False,
        )
    
    def similarity_search(
        self,
        query: str,
        documents: List[str],
        top_k: int = 5,
    ) -> List[Tuple[int, float, str]]:
        """
        Find most similar documents to a query.
        
        Args:
            query: Search query
            documents: List of documents to search
            top_k: Number of results to return
            
        Returns:
            List of (document_index, similarity_score, document_text)
        """
        query_embedding = self.encode_query(query)
        doc_embeddings = self.encode_documents(documents)
        
        # Calculate similarities (dot product since embeddings are normalized)
        similarities = np.dot(doc_embeddings, query_embedding)
        
        # Get top-k indices
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            results.append((
                int(idx),
                float(similarities[idx]),
                documents[idx],
            ))
        
        return results
    
    # LangChain Embeddings interface methods
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Embed documents for LangChain compatibility.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embeddings (each is a list of floats)
        """
        embeddings = self.encode_documents(texts, show_progress=False)
        return embeddings.tolist()
    
    def embed_query(self, text: str) -> List[float]:
        """
        Embed a query for LangChain compatibility.
        
        Args:
            text: Query text
            
        Returns:
            Embedding as list of floats
        """
        embedding = self.encode_query(text)
        return embedding.tolist()

