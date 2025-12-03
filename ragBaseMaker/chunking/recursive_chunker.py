"""
Recursive text splitter that respects document structure.
"""

from typing import List, Dict, Any, Optional
import re

from .base_chunker import BaseChunker, TextChunk


class RecursiveChunker(BaseChunker):
    """
    Recursively splits text using a hierarchy of separators.
    Tries to keep semantically related text together.
    """
    
    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        separators: Optional[List[str]] = None,
    ):
        """
        Initialize the recursive chunker.
        
        Args:
            chunk_size: Target size for each chunk
            chunk_overlap: Overlap between chunks
            separators: List of separators to use, in order of preference
        """
        super().__init__(chunk_size, chunk_overlap)
        
        # Default separators: paragraphs -> sentences -> phrases -> words
        self.separators = separators or [
            '\n\n\n',  # Multiple blank lines (major sections)
            '\n\n',    # Paragraph breaks
            '\n',      # Line breaks
            '. ',      # Sentence endings
            '? ',      # Question marks
            '! ',      # Exclamation marks
            '; ',      # Semicolons
            ', ',      # Commas
            ' ',       # Words
            '',        # Characters (last resort)
        ]
    
    def split(
        self,
        text: str,
        source_path: str = '',
        source_title: str = '',
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[TextChunk]:
        """
        Split text into chunks using recursive splitting.
        """
        if not text.strip():
            return []
        
        chunks = self._split_recursive(text, self.separators)
        
        # Create TextChunk objects
        result: List[TextChunk] = []
        current_pos = 0
        
        for idx, chunk_text in enumerate(chunks):
            if not chunk_text.strip():
                continue
            
            # Find position in original text
            start = text.find(chunk_text, current_pos)
            if start == -1:
                start = current_pos
            end = start + len(chunk_text)
            current_pos = end - self.chunk_overlap
            
            chunk = self._create_chunk(
                text=chunk_text,
                index=idx,
                start_char=start,
                end_char=end,
                source_path=source_path,
                source_title=source_title,
                metadata=metadata,
            )
            result.append(chunk)
        
        return result
    
    def _split_recursive(self, text: str, separators: List[str]) -> List[str]:
        """
        Recursively split text using separators.
        """
        if not separators:
            # No more separators, just split by chunk_size
            return self._split_by_size(text)
        
        separator = separators[0]
        remaining_separators = separators[1:]
        
        # Split by current separator
        if separator == '':
            # Empty separator means split by characters
            return self._split_by_size(text)
        
        splits = text.split(separator)
        
        # If no split occurred, try next separator
        if len(splits) == 1:
            return self._split_recursive(text, remaining_separators)
        
        # Process each split
        chunks: List[str] = []
        current_chunk = ''
        
        for i, split in enumerate(splits):
            # Add separator back (except for first piece)
            if i > 0 and separator.strip():
                split = separator + split
            
            potential_chunk = current_chunk + split
            
            if len(potential_chunk) <= self.chunk_size:
                current_chunk = potential_chunk
            else:
                # Current chunk is full
                if current_chunk:
                    chunks.append(current_chunk)
                
                # If this split alone is too large, recursively split it
                if len(split) > self.chunk_size:
                    sub_chunks = self._split_recursive(split, remaining_separators)
                    chunks.extend(sub_chunks[:-1])
                    current_chunk = sub_chunks[-1] if sub_chunks else ''
                else:
                    current_chunk = split
        
        # Don't forget the last chunk
        if current_chunk:
            chunks.append(current_chunk)
        
        # Add overlaps
        return self._add_overlaps(chunks)
    
    def _split_by_size(self, text: str) -> List[str]:
        """
        Split text into fixed-size chunks.
        """
        if len(text) <= self.chunk_size:
            return [text]
        
        chunks: List[str] = []
        start = 0
        
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            chunks.append(text[start:end])
            start = end - self.chunk_overlap
            
            if start >= len(text):
                break
        
        return chunks
    
    def _add_overlaps(self, chunks: List[str]) -> List[str]:
        """
        Add overlaps between chunks for better context.
        """
        if self.chunk_overlap == 0 or len(chunks) <= 1:
            return chunks
        
        result: List[str] = []
        
        for i, chunk in enumerate(chunks):
            if i > 0:
                # Add overlap from previous chunk
                prev_chunk = chunks[i - 1]
                overlap = prev_chunk[-self.chunk_overlap:]
                
                # Find a good split point in the overlap
                split_point = overlap.rfind(' ')
                if split_point > 0:
                    overlap = overlap[split_point + 1:]
                
                chunk = overlap + chunk
            
            result.append(chunk)
        
        return result

