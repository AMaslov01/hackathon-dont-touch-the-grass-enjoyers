"""
Document loader module using LangChain loaders.
Provides simple interface for loading different document formats.
"""

from typing import List, Optional
from pathlib import Path

from langchain_core.documents import Document
from langchain_community.document_loaders import (
    PyPDFLoader,
    UnstructuredWordDocumentLoader,
    UnstructuredExcelLoader,
    UnstructuredMarkdownLoader,
    TextLoader,
)


class DocumentLoader:
    """
    Simple document loader that automatically selects appropriate LangChain loader.
    Supports: PDF, DOCX, TXT, Markdown.
    """
    
    # Supported file extensions
    SUPPORTED_EXTENSIONS = {
        '.pdf': 'PDF',
        '.docx': 'DOCX',
        '.doc': 'DOCX',
        '.xlsx': 'Excel',
        '.xls': 'Excel',
        '.txt': 'Text',
        '.md': 'Markdown',
        '.markdown': 'Markdown',
    }
    
    @classmethod
    def can_load(cls, file_path: str | Path) -> bool:
        """
        Check if file can be loaded.
        
        Args:
            file_path: Path to file
            
        Returns:
            True if supported format
        """
        path = Path(file_path)
        return path.suffix.lower() in cls.SUPPORTED_EXTENSIONS
    
    @classmethod
    def load(cls, file_path: str | Path) -> List[Document]:
        """
        Load document using appropriate LangChain loader.
        
        Args:
            file_path: Path to document
            
        Returns:
            List of Document objects (one per page/section)
            
        Raises:
            ValueError: If file type not supported
            ImportError: If required dependency not installed
        """
        path = Path(file_path)
        ext = path.suffix.lower()
        
        if not cls.can_load(path):
            supported = ', '.join(cls.SUPPORTED_EXTENSIONS.keys())
            raise ValueError(
                f"Unsupported file type: {ext}\n"
                f"Supported formats: {supported}"
            )
        
        # Select and use appropriate loader
        try:
            if ext == '.pdf':
                loader = PyPDFLoader(str(path))
            
            elif ext in ['.docx', '.doc']:
                loader = UnstructuredWordDocumentLoader(str(path))
            
            elif ext in ['.xlsx', '.xls']:
                loader = UnstructuredExcelLoader(str(path), mode="elements")
            
            elif ext in ['.md', '.markdown']:
                # Use UnstructuredMarkdownLoader for better Markdown parsing
                # It removes formatting (*, **, #, etc.) and extracts clean text
                loader = UnstructuredMarkdownLoader(str(path), mode="elements")
            
            elif ext == '.txt':
                # Plain text - use TextLoader
                try:
                    loader = TextLoader(str(path), encoding='utf-8')
                except UnicodeDecodeError:
                    # Try with autodetection
                    loader = TextLoader(str(path), autodetect_encoding=True)
            
            else:
                # Should not reach here due to can_load check
                raise ValueError(f"Unsupported extension: {ext}")
            
            # Load documents
            docs = loader.load()
            
            # Add source_title to metadata if not present
            for doc in docs:
                if 'source_title' not in doc.metadata:
                    doc.metadata['source_title'] = path.stem
                if 'source' not in doc.metadata:
                    doc.metadata['source'] = str(path)
            
            return docs
        
        except ImportError as e:
            if 'unstructured' in str(e).lower():
                raise ImportError(
                    f"Failed to load {ext} file. Install required packages:\n"
                    f"  pip install unstructured python-docx openpyxl"
                ) from e
            raise
    
    @classmethod
    def load_directory(
        cls,
        directory: str | Path,
        recursive: bool = True,
        extensions: Optional[List[str]] = None,
    ) -> List[tuple[str, List[Document]]]:
        """
        Load all supported documents from directory.
        
        Args:
            directory: Path to directory
            recursive: Search subdirectories
            extensions: Filter by extensions (e.g. ['.pdf', '.txt'])
            
        Returns:
            List of (file_path, documents) tuples
        """
        dir_path = Path(directory)
        
        # Determine which extensions to search for
        if extensions:
            search_exts = {
                ext.lower() if ext.startswith('.') else f'.{ext.lower()}'
                for ext in extensions
            }
        else:
            search_exts = set(cls.SUPPORTED_EXTENSIONS.keys())
        
        # Find all files
        pattern = '**/*' if recursive else '*'
        files = []
        for ext in search_exts:
            files.extend(dir_path.glob(f'{pattern}{ext}'))
        
        # Remove duplicates and sort
        files = sorted(set(files))
        
        # Load each file
        results = []
        for file_path in files:
            try:
                docs = cls.load(file_path)
                results.append((str(file_path), docs))
            except Exception as e:
                # Return error as empty list with error info
                print(f"⚠️ Error loading {file_path.name}: {e}")
                results.append((str(file_path), []))
        
        return results

