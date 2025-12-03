"""
Semantic chunker that uses embeddings to find natural split points.
"""

from typing import List, Dict, Any, Optional, Callable
import re

from ragBaseMaker.chunking.base_chunker import BaseChunker, TextChunk


class SemanticChunker(BaseChunker):
    """
    Splits text based on semantic similarity.
    Uses embeddings to find natural boundaries between topics.
    """
    
    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        embedding_function: Optional[Callable[[str], List[float]]] = None,
        similarity_threshold: float = 0.5,
    ):
        """
        Initialize the semantic chunker.
        
        Args:
            chunk_size: Maximum chunk size
            chunk_overlap: Overlap between chunks
            embedding_function: Function to compute embeddings
            similarity_threshold: Threshold for splitting (lower = more splits)
        """
        super().__init__(chunk_size, chunk_overlap)
        self.embedding_function = embedding_function
        self.similarity_threshold = similarity_threshold
    
    def split(
        self,
        text: str,
        source_path: str = '',
        source_title: str = '',
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[TextChunk]:
        """
        Split text into semantically coherent chunks.
        """
        if not text.strip():
            return []
        
        # First, split into sentences/paragraphs
        segments = self._split_into_segments(text)
        
        if not segments:
            return []
        
        # If we have embedding function, use semantic splitting
        if self.embedding_function:
            chunks = self._semantic_split(segments)
        else:
            # Fallback to size-based merging
            chunks = self._merge_by_size(segments)
        
        # Create TextChunk objects
        result: List[TextChunk] = []
        current_pos = 0
        
        for idx, chunk_text in enumerate(chunks):
            if not chunk_text.strip():
                continue
            
            start = text.find(chunk_text, current_pos)
            if start == -1:
                start = current_pos
            end = start + len(chunk_text)
            current_pos = max(current_pos, end - self.chunk_overlap)
            
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
    
    def _split_into_segments(self, text: str) -> List[str]:
        """
        Split text into small segments (sentences or short paragraphs).
        """
        # Split by sentence-ending punctuation
        sentence_pattern = r'(?<=[.!?])\s+'
        sentences = re.split(sentence_pattern, text)
        
        # Filter and clean
        segments = []
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence:
                segments.append(sentence)
        
        return segments
    
    def _semantic_split(self, segments: List[str]) -> List[str]:
        """
        Use embeddings to find semantic boundaries.
        """
        import numpy as np
        
        # Get embeddings for each segment
        embeddings = []
        for segment in segments:
            try:
                emb = self.embedding_function(segment)
                embeddings.append(emb)
            except Exception:
                # If embedding fails, use zero vector
                embeddings.append([0.0] * 384)  # Default dimension
        
        embeddings = np.array(embeddings)
        
        # Calculate cosine similarity between consecutive segments
        similarities = []
        for i in range(len(embeddings) - 1):
            sim = self._cosine_similarity(embeddings[i], embeddings[i + 1])
            similarities.append(sim)
        
        # Find split points where similarity is low
        split_points = [0]
        current_chunk_size = len(segments[0]) if segments else 0
        
        for i, sim in enumerate(similarities):
            next_segment_size = len(segments[i + 1])
            
            # Split if similarity is below threshold OR chunk would be too large
            should_split = (
                sim < self.similarity_threshold or
                current_chunk_size + next_segment_size > self.chunk_size
            )
            
            if should_split:
                split_points.append(i + 1)
                current_chunk_size = next_segment_size
            else:
                current_chunk_size += next_segment_size
        
        split_points.append(len(segments))
        
        # Create chunks from split points
        chunks = []
        for i in range(len(split_points) - 1):
            start = split_points[i]
            end = split_points[i + 1]
            chunk_text = ' '.join(segments[start:end])
            if chunk_text.strip():
                chunks.append(chunk_text)
        
        return chunks
    
    def _merge_by_size(self, segments: List[str]) -> List[str]:
        """
        Merge segments into chunks based on size.
        """
        chunks = []
        current_chunk = []
        current_size = 0
        
        for segment in segments:
            segment_size = len(segment)
            
            if current_size + segment_size > self.chunk_size and current_chunk:
                chunks.append(' '.join(current_chunk))
                
                # Keep overlap
                overlap_text = current_chunk[-1] if current_chunk else ''
                if len(overlap_text) <= self.chunk_overlap:
                    current_chunk = [overlap_text, segment]
                    current_size = len(overlap_text) + segment_size
                else:
                    current_chunk = [segment]
                    current_size = segment_size
            else:
                current_chunk.append(segment)
                current_size += segment_size
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks
    
    @staticmethod
    def _cosine_similarity(a, b) -> float:
        """Calculate cosine similarity between two vectors."""
        import numpy as np
        
        a = np.array(a)
        b = np.array(b)
        
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot_product / (norm_a * norm_b)

