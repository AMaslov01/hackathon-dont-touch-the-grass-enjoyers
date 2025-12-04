"""
Lightweight translation module for Russian <-> English translation.
Uses Helsinki-NLP OPUS-MT models (fast and efficient).
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Global translator instances
_ru_to_en_translator = None
_en_to_ru_translator = None


class Translator:
    """
    Lightweight translator using Helsinki-NLP OPUS-MT models.
    
    Models:
    - Helsinki-NLP/opus-mt-ru-en (~300MB) - Russian to English
    - Helsinki-NLP/opus-mt-en-ru (~300MB) - English to Russian
    
    These models are:
    - Fast (CPU-friendly)
    - Lightweight (~300MB each)
    - Good quality for RAG context translation
    """
    
    def __init__(
        self,
        ru_to_en_model: str = 'Helsinki-NLP/opus-mt-ru-en',
        en_to_ru_model: str = 'Helsinki-NLP/opus-mt-en-ru',
        device: Optional[str] = None,
    ):
        """
        Initialize translator.
        
        Args:
            ru_to_en_model: Model for Russian -> English translation
            en_to_ru_model: Model for English -> Russian translation
            device: Device to use ('cuda', 'cpu', or None for auto)
        """
        self.ru_to_en_model_name = ru_to_en_model
        self.en_to_ru_model_name = en_to_ru_model
        self.device = device or 'cpu'  # Default to CPU for translation
        
        # Lazy load models
        self._ru_to_en_pipeline = None
        self._en_to_ru_pipeline = None
        
        logger.info(f"Translator initialized (device: {self.device})")
    
    def _load_ru_to_en(self):
        """Lazy load Russian -> English model."""
        if self._ru_to_en_pipeline is not None:
            return
        
        try:
            from transformers import pipeline
            
            logger.info(f"Loading RU->EN model: {self.ru_to_en_model_name}")
            self._ru_to_en_pipeline = pipeline(
                'translation',
                model=self.ru_to_en_model_name,
                device=self.device if self.device == 'cuda' else -1,  # -1 = CPU
            )
            logger.info("RU->EN model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load RU->EN model: {e}")
            raise
    
    def _load_en_to_ru(self):
        """Lazy load English -> Russian model."""
        if self._en_to_ru_pipeline is not None:
            return
        
        try:
            from transformers import pipeline
            
            logger.info(f"Loading EN->RU model: {self.en_to_ru_model_name}")
            self._en_to_ru_pipeline = pipeline(
                'translation',
                model=self.en_to_ru_model_name,
                device=self.device if self.device == 'cuda' else -1,  # -1 = CPU
            )
            logger.info("EN->RU model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load EN->RU model: {e}")
            raise
    
    def translate_ru_to_en(self, text: str, max_length: int = 512) -> str:
        """
        Translate Russian text to English.
        
        Args:
            text: Russian text to translate
            max_length: Maximum length of translation
            
        Returns:
            Translated English text
        """
        if not text or not text.strip():
            return text
        
        try:
            self._load_ru_to_en()
            
            # Split long texts into chunks (OPUS-MT works better with shorter texts)
            chunks = self._split_text(text, max_chunk_size=400)
            translated_chunks = []
            
            for chunk in chunks:
                result = self._ru_to_en_pipeline(
                    chunk,
                    max_length=max_length,
                    truncation=True
                )
                translated_chunks.append(result[0]['translation_text'])
            
            translated = ' '.join(translated_chunks)
            logger.debug(f"Translated RU->EN: {len(text)} chars -> {len(translated)} chars")
            return translated
            
        except Exception as e:
            logger.error(f"Translation RU->EN failed: {e}")
            # Fallback: return original text
            return text
    
    def translate_en_to_ru(self, text: str, max_length: int = 512) -> str:
        """
        Translate English text to Russian.
        
        Args:
            text: English text to translate
            max_length: Maximum length of translation
            
        Returns:
            Translated Russian text
        """
        if not text or not text.strip():
            return text
        
        try:
            self._load_en_to_ru()
            
            # Split long texts into chunks
            chunks = self._split_text(text, max_chunk_size=400)
            translated_chunks = []
            
            for chunk in chunks:
                result = self._en_to_ru_pipeline(
                    chunk,
                    max_length=max_length,
                    truncation=True
                )
                translated_chunks.append(result[0]['translation_text'])
            
            translated = ' '.join(translated_chunks)
            logger.debug(f"Translated EN->RU: {len(text)} chars -> {len(translated)} chars")
            return translated
            
        except Exception as e:
            logger.error(f"Translation EN->RU failed: {e}")
            # Fallback: return original text
            return text
    
    def _split_text(self, text: str, max_chunk_size: int = 400) -> list[str]:
        """
        Split text into chunks for translation.
        
        Args:
            text: Text to split
            max_chunk_size: Maximum chunk size in characters
            
        Returns:
            List of text chunks
        """
        if len(text) <= max_chunk_size:
            return [text]
        
        chunks = []
        current_chunk = []
        current_length = 0
        
        # Split by sentences (simple approach)
        sentences = text.replace('! ', '!|').replace('? ', '?|').replace('. ', '.|').split('|')
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            sentence_len = len(sentence)
            
            if current_length + sentence_len > max_chunk_size:
                if current_chunk:
                    chunks.append(' '.join(current_chunk))
                    current_chunk = [sentence]
                    current_length = sentence_len
                else:
                    # Single sentence is too long, add as is
                    chunks.append(sentence)
            else:
                current_chunk.append(sentence)
                current_length += sentence_len
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks


def get_translator(device: Optional[str] = None) -> Translator:
    """
    Get or create global translator instance (singleton).
    
    Args:
        device: Device to use ('cuda', 'cpu', or None for auto)
        
    Returns:
        Translator instance
    """
    global _ru_to_en_translator, _en_to_ru_translator
    
    # For simplicity, create single Translator instance
    if _ru_to_en_translator is None:
        _ru_to_en_translator = Translator(device=device)
    
    return _ru_to_en_translator


def translate_for_rag(
    query: str,
    context: str,
    direction: str = 'to_en'
) -> tuple[str, str]:
    """
    Translate query and RAG context for better LLM understanding.
    
    Args:
        query: User query (Russian)
        context: RAG context (Russian)
        direction: Translation direction ('to_en' or 'to_ru')
        
    Returns:
        Tuple of (translated_query, translated_context)
    """
    translator = get_translator()
    
    if direction == 'to_en':
        translated_query = translator.translate_ru_to_en(query)
        translated_context = translator.translate_ru_to_en(context)
    else:  # to_ru
        translated_query = translator.translate_en_to_ru(query)
        translated_context = translator.translate_en_to_ru(context)
    
    return translated_query, translated_context

