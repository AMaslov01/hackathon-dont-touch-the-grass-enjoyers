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
    
    # OpenRouter AI Configuration
    OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
    OPENROUTER_API_URL = 'https://openrouter.ai/api/v1/chat/completions'
    AI_MODEL = 'z-ai/glm-4.5-air:free'
    
    # Database Configuration
    DB_HOST = os.getenv('DB_HOST', 'localhost') 
    DB_PORT = os.getenv('DB_PORT', '5432') 
    DB_NAME = os.getenv('DB_NAME', 'telegram_bot') 
    DB_USER = os.getenv('DB_USER', 'postgres') 
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'postgres') 
    
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

