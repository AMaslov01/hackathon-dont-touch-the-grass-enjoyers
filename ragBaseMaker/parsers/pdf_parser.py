"""
PDF document parser using PyPDF2.
"""

from pathlib import Path
from typing import List, Dict, Any

from ragBaseMaker.parsers.base_parser import BaseParser, ParsedDocument


class PDFParser(BaseParser):
    """Parser for PDF documents."""
    
    SUPPORTED_EXTENSIONS = ['.pdf']
    
    def __init__(self, encoding: str = 'utf-8', extract_images: bool = False):
        super().__init__(encoding)
        self.extract_images = extract_images
    
    def parse(self, file_path: str | Path) -> ParsedDocument:
        """
        Parse a PDF document.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            ParsedDocument with extracted text and metadata
        """
        import PyPDF2
        
        path = self._validate_file(file_path)
        
        sections: List[Dict[str, Any]] = []
        all_text_parts: List[str] = []
        metadata: Dict[str, Any] = {}
        
        with open(path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            
            # Extract metadata
            if reader.metadata:
                metadata = {
                    'author': reader.metadata.get('/Author', ''),
                    'creator': reader.metadata.get('/Creator', ''),
                    'producer': reader.metadata.get('/Producer', ''),
                    'subject': reader.metadata.get('/Subject', ''),
                    'title': reader.metadata.get('/Title', ''),
                    'creation_date': str(reader.metadata.get('/CreationDate', '')),
                }
            
            metadata['page_count'] = len(reader.pages)
            
            # Extract text from each page
            for page_num, page in enumerate(reader.pages, 1):
                text = page.extract_text() or ''
                
                if text.strip():
                    sections.append({
                        'type': 'page',
                        'page_number': page_num,
                        'content': text,
                    })
                    all_text_parts.append(f"[Page {page_num}]\n{text}")
        
        content = self._clean_text('\n\n'.join(all_text_parts))
        
        return ParsedDocument(
            content=content,
            source_path=str(path.absolute()),
            file_type='pdf',
            metadata=metadata,
            title=metadata.get('title') or path.stem,
            sections=sections,
        )

