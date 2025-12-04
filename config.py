"""
Configuration management for the bot
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from config.env in the same directory as this file
_BASE_DIR = Path(__file__).resolve().parent
_CONFIG_ENV_PATH = _BASE_DIR / 'config.env'
load_dotenv(dotenv_path=_CONFIG_ENV_PATH)


class Config:
    """Application configuration"""
    
    # Telegram Bot Configuration
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    
    # AI Mode: 'local' or 'openrouter'
    AI_MODE = os.getenv('AI_MODE', 'local')  # Default to local model
    
    # OpenRouter AI Configuration (used when AI_MODE='openrouter')
    OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
    OPENROUTER_API_URL = os.getenv('OPENROUTER_API_URL')
    AI_MODEL = os.getenv('AI_MODEL')
    
    # Local LLM Configuration (used when AI_MODE='local')
    LOCAL_MODEL_PATH = os.getenv('LOCAL_MODEL_PATH')  # Optional: path to pre-downloaded model
    LOCAL_MODEL_THREADS = int(os.getenv('LOCAL_MODEL_THREADS', '16'))  # CPU threads
    LOCAL_MODEL_CONTEXT = int(os.getenv('LOCAL_MODEL_CONTEXT', '4096'))  # Context window
    LOCAL_MODEL_TEMPERATURE = float(os.getenv('LOCAL_MODEL_TEMPERATURE', '0.7'))
    
    # RAG Configuration (using ragBaseMaker)
    RAG_ENABLED = os.getenv('RAG_ENABLED', 'true').lower() == 'true'
    RAG_PERSIST_DIR = os.getenv('RAG_PERSIST_DIR', './rag_data')  # RAG database directory
    RAG_COLLECTION_NAME = os.getenv('RAG_COLLECTION_NAME', 'financial_docs')  # Collection name
    RAG_TOP_K = int(os.getenv('RAG_TOP_K', '3'))  # Number of documents to retrieve
    RAG_MAX_CONTEXT = int(os.getenv('RAG_MAX_CONTEXT', '2000'))  # Max context tokens
    
    # Translation Configuration (for models trained on English data)
    TRANSLATION_ENABLED = os.getenv('TRANSLATION_ENABLED', 'false').lower() == 'true'
    TRANSLATION_DEVICE = os.getenv('TRANSLATION_DEVICE', 'cpu')  # 'cpu' or 'cuda'
    
    # Database Configuration
    DB_HOST = os.getenv('DB_HOST') 
    DB_PORT = os.getenv('DB_PORT') 
    DB_NAME = os.getenv('DB_NAME') 
    DB_USER = os.getenv('DB_USER') 
    DB_PASSWORD = os.getenv('DB_PASSWORD') 
    
    @classmethod
    def get_database_url(cls):
        """Get PostgreSQL connection URL"""
        return f"postgresql://{cls.DB_USER}:{cls.DB_PASSWORD}@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}"
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        if not cls.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")
        if not cls.OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY not found in environment variables")
        return True

