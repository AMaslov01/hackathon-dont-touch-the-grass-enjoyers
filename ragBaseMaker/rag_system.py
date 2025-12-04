"""
Complete RAG (Retrieval-Augmented Generation) System.

This module combines all components:
- Document parsing
- Text chunking
- Embeddings
- Vector database
"""

from typing import List, Dict, Any, Optional, Literal
from pathlib import Path
from dataclasses import dataclass, field

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain.vectorstores import Chroma

try:
    from langchain_experimental.text_splitter import SemanticChunker
    SEMANTIC_CHUNKER_AVAILABLE = True
except ImportError:
    SEMANTIC_CHUNKER_AVAILABLE = False
    SemanticChunker = None

from ragBaseMaker.embeddings import MultilingualEmbedder
from ragBaseMaker.document_loader import DocumentLoader


@dataclass
class SearchResult:
    """Search result from RAG system."""
    text: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


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
        chunker_type: Literal['recursive', 'semantic'] = 'recursive',
    ):
        """
        Initialize the RAG system.
        
        Args:
            persist_directory: Directory to store data
            collection_name: Name of the document collection
            embedding_model: HuggingFace model for embeddings (default: intfloat/multilingual-e5-base)
            chunk_size: Target chunk size in characters (for recursive chunker)
            chunk_overlap: Overlap between chunks (for recursive chunker)
            chunker_type: Type of chunker - 'recursive' (default) or 'semantic'
        """
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        
        # Initialize embedder (needed for semantic chunker)
        self.embedder = MultilingualEmbedder(
            model_name=embedding_model,
            use_query_prefix=('e5' in embedding_model.lower()),
        )
        
        # Initialize chunker based on type
        if chunker_type == 'semantic':
            if not SEMANTIC_CHUNKER_AVAILABLE:
                raise ImportError(
                    "SemanticChunker requires langchain-experimental. "
                    "Install it with: pip install langchain-experimental"
                )
            # MultilingualEmbedder implements LangChain Embeddings interface
            self.chunker = SemanticChunker(
                embeddings=self.embedder,  # Can use directly!
                breakpoint_threshold_type="percentile",  # or "standard_deviation", "interquartile"
            )
            print(f"✅ Using SemanticChunker with {embedding_model}")
        else:
            # Default: recursive chunker
            self.chunker = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                separators=["\n\n\n", "\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " ", ""],
                keep_separator=True,
            )
            print(f"✅ Using RecursiveCharacterTextSplitter (chunk_size={chunk_size})")
        
        # Initialize ChromaDB vector store (using LangChain)
        self.vectorstore = Chroma(
            collection_name=collection_name,
            embedding_function=self.embedder,  # MultilingualEmbedder is LangChain-compatible!
            persist_directory=str(self.persist_directory / 'chroma'),
        )
        print(f"✅ Using ChromaDB at {self.persist_directory / 'chroma'}")
    
    def _load_document(self, file_path: str) -> List[Document]:
        """
        Load document using DocumentLoader.
        
        Args:
            file_path: Path to the document
            
        Returns:
            List of Document objects (pages/sections)
        """
        return DocumentLoader.load(file_path)
    
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
        # Load document using LangChain loader
        docs = self._load_document(file_path)
        
        # Add custom metadata if provided
        if metadata:
            for doc in docs:
                doc.metadata.update(metadata)
        
        # Split documents into chunks
        chunks = self.chunker.split_documents(docs)
        
        if not chunks:
            return 0
        
        # Add to Chroma (handles embeddings automatically!)
        self.vectorstore.add_documents(chunks)
        
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
            extensions: Filter by file extensions (e.g. ['.pdf', '.txt'])
            batch_size: Process N documents at once (not used currently)
            
        Returns:
            Dictionary of file paths to chunk counts
        """
        results = {}
        
        # Use DocumentLoader to find and load all files
        files_with_docs = DocumentLoader.load_directory(
            directory=directory,
            recursive=recursive,
            extensions=extensions
        )
        
        print(f"Found {len(files_with_docs)} documents to process")
        
        for i, (file_path, docs) in enumerate(files_with_docs, 1):
            file_name = Path(file_path).name
            
            if not docs:
                results[file_path] = "Error: Failed to load"
                print(f"[{i}/{len(files_with_docs)}] ✗ {file_name}: Failed to load")
                continue
            
            try:
                # Split into chunks
                chunks = self.chunker.split_documents(docs)
                
                if not chunks:
                    results[file_path] = 0
                    print(f"[{i}/{len(files_with_docs)}] ⚠ {file_name}: 0 chunks")
                    continue
                
                # Add to vector store
                self.vectorstore.add_documents(chunks)
                
                results[file_path] = len(chunks)
                print(f"[{i}/{len(files_with_docs)}] ✓ {file_name}: {len(chunks)} chunks")
                
            except Exception as e:
                results[file_path] = f"Error: {e}"
                print(f"[{i}/{len(files_with_docs)}] ✗ {file_name}: {e}")
        
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
        # Search using Chroma (handles embeddings automatically!)
        search_kwargs = {'k': top_k}
        if filter_metadata:
            search_kwargs['filter'] = filter_metadata
        
        docs_with_scores = self.vectorstore.similarity_search_with_score(
            query, 
            k=top_k,
            filter=filter_metadata
        )
        
        # Convert to SearchResult objects
        results = []
        for doc, score in docs_with_scores:
            # Note: Chroma returns distance, convert to similarity (lower is better)
            # Convert to 0-1 range where higher is better
            similarity = 1.0 / (1.0 + score)
            results.append(SearchResult(
                text=doc.page_content,
                score=similarity,
                metadata=doc.metadata,
            ))
        
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
        collection = self.vectorstore._collection
        return collection.count()
    
    def clear(self) -> None:
        """Clear all documents from the database."""
        # Delete and recreate collection
        collection = self.vectorstore._collection
        collection.delete(where={})  # Delete all documents
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the RAG system."""
        return {
            'available': True,
            'total_chunks': self.count_documents(),
            'persist_directory': str(self.persist_directory),
            'collection_name': self.vectorstore._collection.name,
            'embedding_model': self.embedder.model_name,
        }

