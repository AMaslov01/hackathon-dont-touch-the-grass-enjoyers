"""
Complete RAG (Retrieval-Augmented Generation) System.

This module combines all components:
- Document parsing
- Text chunking
- Embeddings
- Vector database
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import json

from .parsers import UniversalParser, ParsedDocument
from .chunking import RecursiveChunker, TextChunk
from .embeddings import MultilingualEmbedder
from .vectordb import ChromaVectorDB, FAISSVectorDB, SearchResult


class RAGSystem:
    """
    Complete RAG system for document retrieval.
    
    Supports:
    - Multiple document formats (PDF, DOCX, TXT, HTML, etc.)
    - Multilingual embeddings (Russian + English)
    - Persistent vector storage
    """
    
    def __init__(
        self,
        persist_directory: str = './rag_data',
        collection_name: str = 'documents',
        embedding_model: str = 'intfloat/multilingual-e5-base',
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        use_faiss: bool = False,
    ):
        """
        Initialize the RAG system.
        
        Args:
            persist_directory: Directory to store data
            collection_name: Name of the document collection
            embedding_model: HuggingFace model for embeddings
            chunk_size: Target chunk size in characters
            chunk_overlap: Overlap between chunks
            use_faiss: Use FAISS instead of ChromaDB
        """
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.parser = UniversalParser()
        self.chunker = RecursiveChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        self.embedder = MultilingualEmbedder(
            model_name=embedding_model,
            use_query_prefix=('e5' in embedding_model.lower()),
        )
        
        # Initialize vector database
        if use_faiss:
            self.vectordb = FAISSVectorDB(
                collection_name=collection_name,
                embedding_dimension=self.embedder.dimension,
                persist_directory=str(self.persist_directory / 'faiss'),
            )
        else:
            self.vectordb = ChromaVectorDB(
                collection_name=collection_name,
                embedding_dimension=self.embedder.dimension,
                persist_directory=str(self.persist_directory / 'chroma'),
            )
    
    def add_document(
        self,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Add a document to the RAG system.
        
        Args:
            file_path: Path to the document
            metadata: Optional additional metadata
            
        Returns:
            Number of chunks added
        """
        # Parse document
        doc = self.parser.parse(file_path)
        
        # Chunk the document
        chunks = self.chunker.split(
            text=doc.content,
            source_path=doc.source_path,
            source_title=doc.title,
            metadata=metadata,
        )
        
        if not chunks:
            return 0
        
        # Generate embeddings
        texts = [chunk.text for chunk in chunks]
        embeddings = self.embedder.encode_documents(texts, show_progress=True)
        
        # Prepare data for vector DB
        ids = [chunk.chunk_id for chunk in chunks]
        chunk_metadata = [
            {
                'source_path': chunk.source_path,
                'source_title': chunk.source_title,
                'chunk_index': chunk.chunk_index,
                'start_char': chunk.start_char,
                'end_char': chunk.end_char,
                **chunk.metadata,
            }
            for chunk in chunks
        ]
        
        # Add to vector database
        self.vectordb.add(
            ids=ids,
            embeddings=embeddings,
            texts=texts,
            metadata=chunk_metadata,
        )
        
        return len(chunks)
    
    def add_directory(
        self,
        directory: str,
        recursive: bool = True,
        extensions: Optional[List[str]] = None,
        batch_size: int = 10,
    ) -> Dict[str, int]:
        """
        Add all documents from a directory.
        
        Args:
            directory: Path to directory
            recursive: Search subdirectories
            extensions: Filter by file extensions
            batch_size: Process N documents at once (memory optimization)
            
        Returns:
            Dictionary of file paths to chunk counts
        """
        results = {}
        docs = list(self.parser.parse_directory(directory, recursive, extensions))
        
        print(f"Found {len(docs)} documents to process")
        
        for i, doc in enumerate(docs, 1):
            try:
                count = self.add_document(doc.source_path)
                results[doc.source_path] = count
                print(f"[{i}/{len(docs)}] ✓ {doc.source_path}: {count} chunks")
            except Exception as e:
                results[doc.source_path] = f"Error: {e}"
                print(f"[{i}/{len(docs)}] ✗ {doc.source_path}: {e}")
        
        return results
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """
        Search for relevant documents.
        
        Args:
            query: Search query (Russian or English)
            top_k: Number of results
            filter_metadata: Optional metadata filter
            
        Returns:
            List of SearchResult objects
        """
        # Encode query
        query_embedding = self.embedder.encode_query(query)
        
        # Search vector database
        results = self.vectordb.search(
            query_embedding=query_embedding,
            top_k=top_k,
            filter_metadata=filter_metadata,
        )
        
        return results
    
    def get_context(
        self,
        query: str,
        top_k: int = 3,
        max_tokens: int = 2000,
    ) -> str:
        """
        Get context for LLM based on query.
        
        Args:
            query: User query
            top_k: Number of chunks to retrieve
            max_tokens: Approximate maximum tokens in context
            
        Returns:
            Formatted context string
        """
        results = self.search(query, top_k=top_k)
        
        context_parts = []
        total_chars = 0
        max_chars = max_tokens * 4  # Approximate chars to tokens ratio
        
        for result in results:
            if total_chars + len(result.text) > max_chars:
                break
            
            source = result.metadata.get('source_title', 'Unknown')
            context_parts.append(f"[Source: {source}]\n{result.text}")
            total_chars += len(result.text)
        
        return '\n\n---\n\n'.join(context_parts)
    
    def count_documents(self) -> int:
        """Get total number of chunks in the database."""
        return self.vectordb.count()
    
    def clear(self) -> None:
        """Clear all documents from the database."""
        self.vectordb.clear()

