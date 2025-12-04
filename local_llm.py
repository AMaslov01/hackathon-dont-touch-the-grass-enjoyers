"""
Local LLM Manager using llama-cpp-python for Finance RAG model
"""
import logging
import os
from pathlib import Path
from typing import Optional
from llama_cpp import Llama
from huggingface_hub import hf_hub_download

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
    
    def format_chat_prompt(self, system_message: str, user_message: str) -> str:
        """
        Format messages using Llama-3 chat template
        
        Args:
            system_message: System prompt
            user_message: User message
            
        Returns:
            Formatted prompt string
        """
        prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

{system_message}<|eot_id|><|start_header_id|>user<|end_header_id|>

{user_message}<|eot_id|><|start_header_id|>assistant<|end_header_id|>

"""
        return prompt
    
    def chat(self, system_message: str, user_message: str, max_tokens: int = 512,
             temperature: float = 0.7) -> str:
        """
        Generate chat response
        
        Args:
            system_message: System prompt
            user_message: User message
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            
        Returns:
            Assistant's response
        """
        prompt = self.format_chat_prompt(system_message, user_message)
        return self.generate(prompt, max_tokens=max_tokens, temperature=temperature)
    
    def unload_model(self):
        """Unload model from memory"""
        if self.model is not None:
            del self.model
            self.model = None
            logger.info("Model unloaded from memory")


# Global instance (lazy loading)
_local_llm_instance = None


def get_local_llm(n_threads: int = 16) -> LocalLLM:
    """
    Get or create global LocalLLM instance
    
    Args:
        n_threads: Number of CPU threads (default: 16)
        
    Returns:
        LocalLLM instance
    """
    global _local_llm_instance
    
    if _local_llm_instance is None:
        _local_llm_instance = LocalLLM(n_threads=n_threads)
        _local_llm_instance.load_model()
    
    return _local_llm_instance

