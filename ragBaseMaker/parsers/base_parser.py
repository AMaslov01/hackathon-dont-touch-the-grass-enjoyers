"""
Base parser class for document parsing.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class ParsedDocument:
    """Represents a parsed document with metadata."""
    
    content: str  # Extracted text content
    source_path: str  # Original file path
    file_type: str  # File extension/type
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Document structure
    title: Optional[str] = None
    sections: List[Dict[str, Any]] = field(default_factory=list)
    
    # Timestamps
    parsed_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        if not self.title:
            self.title = Path(self.source_path).stem
    
    @property
    def word_count(self) -> int:
        """Count words in the document."""
        return len(self.content.split())
    
    @property
    def char_count(self) -> int:
        """Count characters in the document."""
        return len(self.content)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'content': self.content,
            'source_path': self.source_path,
            'file_type': self.file_type,
            'metadata': self.metadata,
            'title': self.title,
            'sections': self.sections,
            'parsed_at': self.parsed_at.isoformat(),
            'word_count': self.word_count,
            'char_count': self.char_count,
        }


class BaseParser(ABC):
    """
    Abstract base class for document parsers.
    All parsers should inherit from this class.
    """
    
    # Supported file extensions for this parser
    SUPPORTED_EXTENSIONS: List[str] = []
    
    def __init__(self, encoding: str = 'utf-8'):
        self.encoding = encoding
    
    @abstractmethod
    def parse(self, file_path: str | Path) -> ParsedDocument:
        """
        Parse a document and return ParsedDocument.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            ParsedDocument with extracted content and metadata
        """
        pass
    
    def can_parse(self, file_path: str | Path) -> bool:
        """
        Check if this parser can handle the given file.
        
        Args:
            file_path: Path to check
            
        Returns:
            True if this parser supports the file type
        """
        path = Path(file_path)
        return path.suffix.lower() in self.SUPPORTED_EXTENSIONS
    
    def _validate_file(self, file_path: str | Path) -> Path:
        """
        Validate that file exists and is readable.
        
        Args:
            file_path: Path to validate
            
        Returns:
            Validated Path object
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file type is not supported
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if not path.is_file():
            raise ValueError(f"Not a file: {file_path}")
        
        if not self.can_parse(path):
            raise ValueError(
                f"Unsupported file type: {path.suffix}. "
                f"Supported: {self.SUPPORTED_EXTENSIONS}"
            )
        
        return path
    
    def _clean_text(self, text: str) -> str:
        """
        Clean extracted text by removing excessive whitespace.
        
        Args:
            text: Raw extracted text
            
        Returns:
            Cleaned text
        """
        import re
        
        # Replace multiple newlines with double newline
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Replace multiple spaces with single space
        text = re.sub(r' {2,}', ' ', text)
        
        # Remove leading/trailing whitespace from each line
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)
        
        return text.strip()

