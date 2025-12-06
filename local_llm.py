"""
Local LLM Manager using llama-cpp-python with multi-model support
Supports loading/unloading multiple models with LRU caching
"""
import logging
import os
from pathlib import Path
from typing import Optional, Dict
from llama_cpp import Llama
from huggingface_hub import hf_hub_download
from collections import OrderedDict
from threading import Lock

logger = logging.getLogger(__name__)


class LocalLLM:
    """Manager for local Llama model with GGUF format"""
    
    def __init__(self, model_path: Optional[str] = None, n_ctx: int = 4096, n_threads: int = 16):
        """
        Initialize Local LLM
        
        Args:
            model_path: Path to GGUF model file (downloads if not exists)
            n_ctx: Context window size (default: 4096)
            n_threads: Number of CPU threads to use (default: 16)
        """
        self.model_path = model_path
        self.n_ctx = n_ctx
        self.n_threads = n_threads
        self.model = None
        
        # Model configuration
        self.repo_id = "QuantFactory/Llama-3-8B-Instruct-Finance-RAG-GGUF"
        self.filename = "Llama-3-8B-Instruct-Finance-RAG.Q4_K_M.gguf"  # 4.92GB - optimal for CPU
        
    def download_model(self) -> str:
        """
        Download model from HuggingFace if not exists
        
        Returns:
            Path to downloaded model file
        """
        if self.model_path and os.path.exists(self.model_path):
            logger.info(f"Using existing model at: {self.model_path}")
            return self.model_path
        
        # Create models directory
        models_dir = Path(__file__).parent / "models"
        models_dir.mkdir(exist_ok=True)
        
        local_path = models_dir / self.filename
        
        if local_path.exists():
            logger.info(f"Model already exists at: {local_path}")
            return str(local_path)
        
        logger.info(f"Downloading model from HuggingFace: {self.repo_id}/{self.filename}")
        logger.info("This may take a while (model size: ~5GB)...")

        try:
            downloaded_path = hf_hub_download(
                repo_id=self.repo_id,
                filename=self.filename,
                cache_dir=str(models_dir),
                resume_download=True
            )
            logger.info(f"Model downloaded successfully to: {downloaded_path}")
            return downloaded_path
            
        except Exception as e:
            logger.error(f"Failed to download model: {e}")
            raise
    
    def load_model(self):
        """Load the GGUF model into memory"""
        if self.model is not None:
            logger.info("Model already loaded")
            return
        
        try:
            # Download model if needed
            model_path = self.download_model()
            
            logger.info(f"Loading model from: {model_path}")
            logger.info(f"Using {self.n_threads} CPU threads with {self.n_ctx} context window")
            
            self.model = Llama(
                model_path=model_path,
                n_ctx=self.n_ctx,
                n_threads=self.n_threads,
                n_batch=512,  # Batch size for prompt processing
                verbose=False
            )
            
            logger.info("Model loaded successfully!")
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    
    def generate(self, prompt: str, max_tokens: int = 512, temperature: float = 0.7,
                 top_p: float = 0.9, stop: Optional[list] = None) -> str:
        """
        Generate text using the local model
        
        Args:
            prompt: Input prompt (should be formatted with Llama-3 chat template)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0-1.0)
            top_p: Nucleus sampling parameter
            stop: List of stop sequences
            
        Returns:
            Generated text
        """
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")
        
        try:
            logger.info(f"Generating response (max_tokens={max_tokens}, temp={temperature})")
            
            response = self.model(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                stop=stop or ["<|eot_id|>"],
                echo=False
            )
            
            generated_text = response['choices'][0]['text'].strip()
            logger.info(f"Generated {len(generated_text)} characters")
            
            return generated_text
            
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            raise
    
    def format_chat_prompt(self, system_message: str, user_message: str, prompt_format: str = "llama3") -> str:
        """
        Format messages using specified chat template
        
        Args:
            system_message: System prompt
            user_message: User message
            prompt_format: Format type ('llama3' or 'qwen')
            
        Returns:
            Formatted prompt string
        """
        if prompt_format == "qwen":
            # Qwen2.5 format
            prompt = f"""<|im_start|>system
{system_message}<|im_end|>
<|im_start|>user
{user_message}<|im_end|>
<|im_start|>assistant
"""
        else:
            # Llama-3 format (default)
            # Note: <|begin_of_text|> is automatically added by llama-cpp-python, don't add it manually
            prompt = f"""<|start_header_id|>system<|end_header_id|>

{system_message}<|eot_id|><|start_header_id|>user<|end_header_id|>

{user_message}<|eot_id|><|start_header_id|>assistant<|end_header_id|>

"""
        return prompt
    
    def chat(self, system_message: str, user_message: str, max_tokens: int = 512,
             temperature: float = 0.7, prompt_format: str = "llama3", stop_tokens: Optional[list] = None) -> str:
        """
        Generate chat response
        
        Args:
            system_message: System prompt
            user_message: User message
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            prompt_format: Format type ('llama3' or 'qwen')
            stop_tokens: Custom stop tokens (overrides default)
            
        Returns:
            Assistant's response
        """
        prompt = self.format_chat_prompt(system_message, user_message, prompt_format)
        return self.generate(prompt, max_tokens=max_tokens, temperature=temperature, stop=stop_tokens)
    
    def unload_model(self):
        """Unload model from memory"""
        if self.model is not None:
            del self.model
            self.model = None
            logger.info("Model unloaded from memory")


# =============================================================================
# MULTI-MODEL MANAGER
# =============================================================================

class LocalLLMManager:
    """
    Менеджер для управления несколькими локальными моделями
    
    Использует LRU кэш для автоматической выгрузки неиспользуемых моделей.
    По умолчанию держит до 2 моделей в памяти (~10GB RAM).
    """
    
    def __init__(self, max_loaded_models: int = 2, n_threads: int = 16, n_ctx: int = 4096):
        """
        Initialize model manager
        
        Args:
            max_loaded_models: Максимум моделей в памяти (по умолчанию 2)
            n_threads: CPU threads для каждой модели
            n_ctx: Context window для каждой модели
        """
        self.max_loaded_models = max_loaded_models
        self.n_threads = n_threads
        self.n_ctx = n_ctx
        
        # LRU кэш загруженных моделей: {model_id: LocalLLM}
        self._loaded_models: OrderedDict[str, LocalLLM] = OrderedDict()
        self._lock = Lock()
        
        logger.info(f"LocalLLMManager initialized (max_models={max_loaded_models}, threads={n_threads})")
    
    def get_model(self, model_id: str, repo_id: str, filename: str) -> LocalLLM:
        """
        Получить модель (загрузить если не загружена)
        
        Args:
            model_id: ID модели
            repo_id: HuggingFace repo ID
            filename: Filename модели
        
        Returns:
            Загруженная модель
        """
        with self._lock:
            # Если модель уже загружена - переместить в конец (LRU)
            if model_id in self._loaded_models:
                logger.info(f"Model {model_id} already loaded, using cached")
                self._loaded_models.move_to_end(model_id)
                return self._loaded_models[model_id]
            
            # Если достигнут лимит - выгрузить самую старую модель
            if len(self._loaded_models) >= self.max_loaded_models:
                oldest_id = next(iter(self._loaded_models))
                logger.info(f"Unloading oldest model: {oldest_id}")
                oldest_model = self._loaded_models.pop(oldest_id)
                oldest_model.unload_model()
            
            # Загрузить новую модель
            logger.info(f"Loading new model: {model_id}")
            llm = LocalLLM(
                model_path=None,
                n_ctx=self.n_ctx,
                n_threads=self.n_threads
            )
            llm.repo_id = repo_id
            llm.filename = filename
            llm.load_model()
            
            # Добавить в кэш
            self._loaded_models[model_id] = llm
            logger.info(f"Model {model_id} loaded successfully")
            
            return llm
    
    def unload_model(self, model_id: str):
        """Выгрузить конкретную модель из памяти"""
        with self._lock:
            if model_id in self._loaded_models:
                logger.info(f"Unloading model: {model_id}")
                model = self._loaded_models.pop(model_id)
                model.unload_model()
    
    def unload_all(self):
        """Выгрузить все модели из памяти"""
        with self._lock:
            logger.info("Unloading all models")
            for model_id, model in self._loaded_models.items():
                model.unload_model()
            self._loaded_models.clear()
    
    def get_loaded_models(self) -> list[str]:
        """Получить список ID загруженных моделей"""
        return list(self._loaded_models.keys())


# Global manager instance
_model_manager = None
_manager_lock = Lock()


def get_model_manager(max_models: int = 2, n_threads: int = 16) -> LocalLLMManager:
    """
    Get or create global model manager instance
    
    Args:
        max_models: Maximum models in memory
        n_threads: CPU threads per model
    
    Returns:
        LocalLLMManager instance
    """
    global _model_manager
    
    with _manager_lock:
        if _model_manager is None:
            _model_manager = LocalLLMManager(
                max_loaded_models=max_models,
                n_threads=n_threads
            )
        
        return _model_manager


# =============================================================================
# LEGACY SUPPORT (для обратной совместимости)
# =============================================================================

# Global instance (lazy loading) - DEPRECATED
_local_llm_instance = None


def get_local_llm(n_threads: int = 16) -> LocalLLM:
    """
    Get or create global LocalLLM instance (LEGACY)
    
    DEPRECATED: Use get_model_manager() instead
    
    Args:
        n_threads: Number of CPU threads (default: 16)
        
    Returns:
        LocalLLM instance
    """
    global _local_llm_instance
    
    if _local_llm_instance is None:
        logger.warning("get_local_llm() is deprecated, use get_model_manager() instead")
        _local_llm_instance = LocalLLM(n_threads=n_threads)
        _local_llm_instance.load_model()
    
    return _local_llm_instance

