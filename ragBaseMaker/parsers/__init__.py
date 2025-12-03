"""
Document parsers module for RAG system.
Supports: PDF, DOCX, TXT, MD, HTML, XLSX, PPTX
"""

from .base_parser import BaseParser, ParsedDocument
from .pdf_parser import PDFParser
from .docx_parser import DOCXParser
from .text_parser import TextParser
from .html_parser import HTMLParser
from .excel_parser import ExcelParser
from .pptx_parser import PPTXParser
from .universal_parser import UniversalParser

__all__ = [
    'BaseParser',
    'ParsedDocument',
    'PDFParser',
    'DOCXParser',
    'TextParser',
    'HTMLParser',
    'ExcelParser',
    'PPTXParser',
    'UniversalParser',
]
