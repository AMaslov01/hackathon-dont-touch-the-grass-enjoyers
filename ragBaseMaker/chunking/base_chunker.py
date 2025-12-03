"""
Base chunker class for text splitting.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import hashlib


@dataclass
class TextChunk:
    """Represents a chunk of text with metadata."""
    
    text: str  # The chunk content
    chunk_index: int  # Position in the document
    
    # Source information
    source_path: str = ''
    source_title: str = ''
    
    # Chunk metadata
    start_char: int = 0  # Starting character position in source
    end_char: int = 0  # Ending character position in source
    
    # Optional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def chunk_id(self) -> str:
        """Generate unique ID for this chunk."""
        content = f"{self.source_path}:{self.chunk_index}:{self.text[:100]}"
        return hashlib.md5(content.encode()).hexdigest()
    
    @property
    def word_count(self) -> int:
        """Count words in the chunk."""
        return len(self.text.split())
    
    @property
    def char_count(self) -> int:
        """Count characters in the chunk."""
        return len(self.text)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'chunk_id': self.chunk_id,
            'text': self.text,
            'chunk_index': self.chunk_index,
            'source_path': self.source_path,
            'source_title': self.source_title,
            'start_char': self.start_char,
            'end_char': self.end_char,
            'word_count': self.word_count,
            'char_count': self.char_count,
            'metadata': self.metadata,
        }


class BaseChunker(ABC):
    """
    Abstract base class for text chunkers.
    """
    
    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
    ):
        """
        Initialize the chunker.
        
        Args:
            chunk_size: Target size for each chunk (in characters)
            chunk_overlap: Number of characters to overlap between chunks
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    @abstractmethod
    def split(
        self,
        text: str,
        source_path: str = '',
        source_title: str = '',
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[TextChunk]:
        """
        Split text into chunks.
        
        Args:
            text: The text to split
            source_path: Path to the source document
            source_title: Title of the source document
            metadata: Additional metadata to attach to each chunk
            
        Returns:
            List of TextChunk objects
        """
        pass
    
    def _create_chunk(
        self,
        text: str,
        index: int,
        start_char: int,
        end_char: int,
        source_path: str,
        source_title: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TextChunk:
        """
        Create a TextChunk with proper metadata.
        """
        return TextChunk(
            text=text.strip(),
            chunk_index=index,
            source_path=source_path,
            source_title=source_title,
            start_char=start_char,
            end_char=end_char,
            metadata=metadata or {},
        )

