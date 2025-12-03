"""
Universal parser that automatically selects the appropriate parser based on file type.
"""

from pathlib import Path
from typing import List, Optional, Type

from ragBaseMaker.parsers.base_parser import BaseParser, ParsedDocument
from ragBaseMaker.parsers.pdf_parser import PDFParser
from ragBaseMaker.parsers.docx_parser import DOCXParser
from ragBaseMaker.parsers.text_parser import TextParser
from ragBaseMaker.parsers.html_parser import HTMLParser
from ragBaseMaker.parsers.excel_parser import ExcelParser
from ragBaseMaker.parsers.pptx_parser import PPTXParser


class UniversalParser:
    """
    Universal document parser that automatically detects file type
    and uses the appropriate parser.
    """
    
    def __init__(self):
        # Parser classes (not instances) - lazy loading
        self._parser_classes: dict[str, Type[BaseParser]] = {
            '.pdf': PDFParser,
            '.docx': DOCXParser,
            '.doc': DOCXParser,
            '.txt': TextParser,
            '.md': TextParser,
            '.html': HTMLParser,
            '.htm': HTMLParser,
            '.xlsx': ExcelParser,
            '.xls': ExcelParser,
            '.pptx': PPTXParser,
            '.ppt': PPTXParser,
        }
        
        # Cache for instantiated parsers
        self._parser_cache: dict[str, BaseParser] = {}
    
    @property
    def supported_extensions(self) -> List[str]:
        """Get all supported file extensions."""
        return sorted(self._parser_classes.keys())
    
    def can_parse(self, file_path: str | Path) -> bool:
        """Check if the file can be parsed."""
        path = Path(file_path)
        return path.suffix.lower() in self._parser_classes
    
    def get_parser(self, file_path: str | Path) -> Optional[BaseParser]:
        """Get the appropriate parser for a file (lazy instantiation)."""
        path = Path(file_path)
        ext = path.suffix.lower()
        
        # Return cached parser if exists
        if ext in self._parser_cache:
            return self._parser_cache[ext]
        
        # Instantiate new parser
        parser_class = self._parser_classes.get(ext)
        if parser_class:
            parser = parser_class()
            self._parser_cache[ext] = parser
            return parser
        
        return None
    
    def parse(self, file_path: str | Path) -> ParsedDocument:
        """
        Parse a document using the appropriate parser.
        
        Args:
            file_path: Path to the document
            
        Returns:
            ParsedDocument with extracted content
            
        Raises:
            ValueError: If file type is not supported
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        parser = self.get_parser(path)
        
        if parser is None:
            raise ValueError(
                f"Unsupported file type: {path.suffix}. "
                f"Supported extensions: {self.supported_extensions}"
            )
        
        return parser.parse(path)
    
    def parse_directory(
        self,
        directory: str | Path,
        recursive: bool = True,
        extensions: Optional[List[str]] = None,
    ) -> List[ParsedDocument]:
        """
        Parse all supported documents in a directory.
        
        Args:
            directory: Path to the directory
            recursive: Whether to search subdirectories
            extensions: Filter to specific extensions (optional)
            
        Returns:
            List of ParsedDocument objects
        """
        directory = Path(directory)
        
        if not directory.is_dir():
            raise ValueError(f"Not a directory: {directory}")
        
        # Determine which extensions to look for
        target_extensions = set(extensions or self.supported_extensions)
        target_extensions = {ext.lower() for ext in target_extensions}
        
        # Find all matching files
        documents: List[ParsedDocument] = []
        
        if recursive:
            files = directory.rglob('*')
        else:
            files = directory.glob('*')
        
        for file_path in files:
            if file_path.is_file() and file_path.suffix.lower() in target_extensions:
                try:
                    doc = self.parse(file_path)
                    documents.append(doc)
                except Exception as e:
                    print(f"Warning: Failed to parse {file_path}: {e}")
        
        return documents
    
    def register_parser(self, parser_class: Type[BaseParser], extensions: List[str]) -> None:
        """
        Register a custom parser class.
        
        Args:
            parser_class: Parser class (not instance) to register
            extensions: File extensions this parser supports
        """
        for ext in extensions:
            ext = ext.lower()
            self._parser_classes[ext] = parser_class
            # Clear cache for this extension
            self._parser_cache.pop(ext, None)

