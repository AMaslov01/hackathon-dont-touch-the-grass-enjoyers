"""
Plain text and Markdown document parser.
"""

from pathlib import Path
from typing import List, Dict, Any
import re

from ragBaseMaker.parsers.base_parser import BaseParser, ParsedDocument


class TextParser(BaseParser):
    """Parser for plain text and Markdown files."""
    
    SUPPORTED_EXTENSIONS = ['.txt', '.md', '.markdown', '.rst', '.text']
    
    def __init__(self, encoding: str = 'utf-8', detect_encoding: bool = True):
        super().__init__(encoding)
        self.detect_encoding = detect_encoding
    
    def _detect_file_encoding(self, file_path: Path) -> str:
        """Detect file encoding using chardet."""
        if not self.detect_encoding:
            return self.encoding
        
        try:
            import chardet
            
            with open(file_path, 'rb') as f:
                raw_data = f.read()
                result = chardet.detect(raw_data)
                return result.get('encoding', self.encoding) or self.encoding
        except ImportError:
            return self.encoding
    
    def parse(self, file_path: str | Path) -> ParsedDocument:
        """
        Parse a text or Markdown document.
        
        Args:
            file_path: Path to text file
            
        Returns:
            ParsedDocument with extracted text and metadata
        """
        path = self._validate_file(file_path)
        
        # Detect encoding
        encoding = self._detect_file_encoding(path)
        
        # Read file
        with open(path, 'r', encoding=encoding, errors='replace') as f:
            content = f.read()
        
        sections: List[Dict[str, Any]] = []
        metadata: Dict[str, Any] = {
            'encoding': encoding,
            'file_size': path.stat().st_size,
        }
        
        # Check if it's Markdown and extract structure
        if path.suffix.lower() in ['.md', '.markdown']:
            metadata['format'] = 'markdown'
            sections = self._parse_markdown_structure(content)
        else:
            metadata['format'] = 'plain_text'
            sections = self._parse_text_structure(content)
        
        content = self._clean_text(content)
        
        # Try to extract title from content
        title = self._extract_title(content, path.suffix.lower())
        
        return ParsedDocument(
            content=content,
            source_path=str(path.absolute()),
            file_type=path.suffix.lower().lstrip('.'),
            metadata=metadata,
            title=title or path.stem,
            sections=sections,
        )
    
    def _parse_markdown_structure(self, content: str) -> List[Dict[str, Any]]:
        """Extract sections from Markdown content."""
        sections: List[Dict[str, Any]] = []
        
        # Split by headers
        header_pattern = r'^(#{1,6})\s+(.+)$'
        
        lines = content.split('\n')
        current_section = {'level': 0, 'heading': None, 'content': []}
        
        for line in lines:
            match = re.match(header_pattern, line)
            if match:
                # Save previous section
                if current_section['heading'] or current_section['content']:
                    sections.append({
                        'type': 'section',
                        'level': current_section['level'],
                        'heading': current_section['heading'],
                        'content': '\n'.join(current_section['content']),
                    })
                
                level = len(match.group(1))
                heading = match.group(2).strip()
                current_section = {'level': level, 'heading': heading, 'content': []}
            else:
                current_section['content'].append(line)
        
        # Add last section
        if current_section['heading'] or current_section['content']:
            sections.append({
                'type': 'section',
                'level': current_section['level'],
                'heading': current_section['heading'],
                'content': '\n'.join(current_section['content']),
            })
        
        return sections
    
    def _parse_text_structure(self, content: str) -> List[Dict[str, Any]]:
        """Extract paragraphs from plain text."""
        sections: List[Dict[str, Any]] = []
        
        # Split by double newlines (paragraphs)
        paragraphs = re.split(r'\n\s*\n', content)
        
        for idx, para in enumerate(paragraphs, 1):
            para = para.strip()
            if para:
                sections.append({
                    'type': 'paragraph',
                    'number': idx,
                    'content': para,
                })
        
        return sections
    
    def _extract_title(self, content: str, extension: str) -> str | None:
        """Try to extract document title from content."""
        lines = content.strip().split('\n')
        
        if not lines:
            return None
        
        first_line = lines[0].strip()
        
        # Markdown title
        if extension in ['.md', '.markdown']:
            match = re.match(r'^#\s+(.+)$', first_line)
            if match:
                return match.group(1).strip()
        
        # If first line looks like a title (short, no period)
        if len(first_line) < 100 and not first_line.endswith('.'):
            return first_line
        
        return None

