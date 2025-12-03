"""
Document parsers module for RAG system.
Supports: PDF, DOCX, TXT, MD, HTML, XLSX, PPTX
"""

from ragBaseMaker.parsers.base_parser import BaseParser, ParsedDocument
from ragBaseMaker.parsers.pdf_parser import PDFParser
from ragBaseMaker.parsers.docx_parser import DOCXParser
from ragBaseMaker.parsers.text_parser import TextParser
from ragBaseMaker.parsers.html_parser import HTMLParser
from ragBaseMaker.parsers.excel_parser import ExcelParser
from ragBaseMaker.parsers.pptx_parser import PPTXParser
from ragBaseMaker.parsers.universal_parser import UniversalParser

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
