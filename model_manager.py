"""
Model Manager - система управления локальными и облачными моделями
Поддерживает бесплатные и премиум модели
"""
import logging
from enum import Enum
from typing import Optional, Dict
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


def escape_markdown(text: str) -> str:
    """
    Escape special Markdown characters.
    
    Args:
        text: The text to escape
        
    Returns:
        Text with escaped Markdown special characters
    """
    if not text:
        return text
    
    special_chars = ['_', '*', '[', ']', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '!']
    for char in special_chars:
        text = text.replace(char, '\\' + char)
    
    return text


class ModelTier(Enum):
    """Уровни доступа к моделям"""
    FREE = "free"
    PREMIUM = "premium"


class ModelType(Enum):
    """Типы моделей"""
    LOCAL = "local"
    OPENROUTER = "openrouter"


@dataclass
class ModelConfig:
    """Конфигурация модели"""
    id: str  # Уникальный ID модели
    name: str  # Отображаемое имя
    tier: ModelTier  # Уровень доступа
    model_type: ModelType  # Тип модели
    description: str  # Описание для пользователя
    
    # Для локальных моделей
    repo_id: Optional[str] = None
    filename: Optional[str] = None
    prompt_format: Optional[str] = None  # 'llama3' или 'qwen'
    stop_tokens: Optional[list] = None
    
    # Для OpenRouter моделей
    openrouter_id: Optional[str] = None


# =============================================================================
# КОНФИГУРАЦИИ МОДЕЛЕЙ
# =============================================================================

MODELS: Dict[str, ModelConfig] = {
    # =========================================================================
    # БЕСПЛАТНЫЕ ЛОКАЛЬНЫЕ МОДЕЛИ
    # =========================================================================
    "llama3-finance": ModelConfig(
        id="llama3-finance",
        name="Llama-3 Finance (Бесплатная)",
        tier=ModelTier.FREE,
        model_type=ModelType.LOCAL,
        description="Базовая модель, специализированная на финансовом анализе. Обучена на английском (может быть хуже на русском).",
        repo_id="QuantFactory/Llama-3-8B-Instruct-Finance-RAG-GGUF",
        filename="Llama-3-8B-Instruct-Finance-RAG.Q4_K_M.gguf",
        prompt_format="llama3",
        stop_tokens=["<|eot_id|>"]
    ),
    
    # =========================================================================
    # ПРЕМИУМ ЛОКАЛЬНЫЕ МОДЕЛИ
    # =========================================================================
    "qwen2.5-7b": ModelConfig(
        id="qwen2.5-7b",
        name="Qwen2.5-7B (Премиум)",
        tier=ModelTier.PREMIUM,
        model_type=ModelType.LOCAL,
        description="⭐ Премиум модель с отличным русским языком. Быстрая и качественная генерация. Идеальна для финансовых планов с таблицами.",
        repo_id="Qwen/Qwen2.5-7B-Instruct-GGUF",
        filename="qwen2_5-7b-instruct-q4_k_m.gguf",
        prompt_format="qwen",
        stop_tokens=["<|im_end|>", "<|endoftext|>"]
    ),
    
    # =========================================================================
    # БЕСПЛАТНЫЕ OPENROUTER МОДЕЛИ
    # =========================================================================
    "deepseek-chimera": ModelConfig(
        id="deepseek-v3",
        name="DeepSeek V3 (Премиум)",
        tier=ModelTier.PREMIUM,
        model_type=ModelType.OPENROUTER,
        description="⭐ DeepSeek chimera - мощная модель с контекстом 64K токенов.",
        openrouter_id="tngtech/deepseek-r1t2-chimera:free"  # БЕСПЛАТНАЯ на OpenRouter!
    ),
    
    
    # =========================================================================
    # ПРЕМИУМ OPENROUTER МОДЕЛИ (облачные, требуют реальной оплаты на OpenRouter)
    # =========================================================================
    
    "meta-llama": ModelConfig(
        id="meta-llama",
        name="meta-llama (Премиум)",
        tier=ModelTier.PREMIUM,
        model_type=ModelType.OPENROUTER,
        description="⭐ meta-llama/llama - быстрая экспериментальная модель от Google.",
        openrouter_id="meta-llama/llama-3.3-70b-instruct:free"  # БЕСПЛАТНАЯ на OpenRouter!
    ),
    
    "glm-4.5-air": ModelConfig(
        id="glm-4.5-air",
        name="GLM-4.5-Air (Бесплатная)",
        tier=ModelTier.FREE,
        model_type=ModelType.OPENROUTER,
        description="Быстрая облачная модель для общих задач. Требует интернет.",
        openrouter_id="z-ai/glm-4.5-air:free"
    ),
    
    
    
}


# Дефолтные модели для новых пользователей (зависит от режима работы)
DEFAULT_MODEL_ID_LOCAL = "llama3-finance"  # Для режима local
DEFAULT_MODEL_ID_OPENROUTER = "deepseek-chimera"  # Для режима openrouter


def get_default_model_id(ai_mode: str = "local") -> str:
    """
    Получить дефолтную модель в зависимости от режима работы
    
    Args:
        ai_mode: 'local' или 'openrouter'
    
    Returns:
        ID дефолтной модели
    """
    if ai_mode == "openrouter":
        return DEFAULT_MODEL_ID_OPENROUTER
    else:
        return DEFAULT_MODEL_ID_LOCAL


# Обратная совместимость: старая константа DEFAULT_MODEL_ID
# DEPRECATED: используйте get_default_model_id(ai_mode) вместо этого
DEFAULT_MODEL_ID = DEFAULT_MODEL_ID_LOCAL


def get_model_config(model_id: str) -> Optional[ModelConfig]:
    """Получить конфигурацию модели по ID"""
    return MODELS.get(model_id)


def get_free_models() -> Dict[str, ModelConfig]:
    """Получить список бесплатных моделей"""
    return {k: v for k, v in MODELS.items() if v.tier == ModelTier.FREE}


def get_premium_models() -> Dict[str, ModelConfig]:
    """Получить список премиум моделей"""
    return {k: v for k, v in MODELS.items() if v.tier == ModelTier.PREMIUM}


def get_local_models() -> Dict[str, ModelConfig]:
    """Получить список локальных моделей"""
    return {k: v for k, v in MODELS.items() if v.model_type == ModelType.LOCAL}


def get_openrouter_models() -> Dict[str, ModelConfig]:
    """Получить список OpenRouter моделей"""
    return {k: v for k, v in MODELS.items() if v.model_type == ModelType.OPENROUTER}


def format_models_list(models: Dict[str, ModelConfig], show_price: bool = True) -> str:
    """
    Форматировать список моделей для отображения пользователю
    
    Args:
        models: Словарь моделей
        show_price: Показывать ли цену
    
    Returns:
        Отформатированный текст
    """
    from constants import TOKEN_CONFIG
    
    result = []
    
    for model_id, config in models.items():
        # Эмодзи не в начале строки - избегаем проблем с Markdown парсером
        tier_text = "PREMIUM" if config.tier == ModelTier.PREMIUM else "FREE"
        type_text = "LOCAL" if config.model_type == ModelType.LOCAL else "CLOUD"
        
        # Безопасный формат: текст -> эмодзи -> markdown
        line = f"[{tier_text}] [{type_text}] *{config.name}*\n"
        line += f"{config.description}\n"
        
        if show_price and config.tier == ModelTier.PREMIUM:
            price = TOKEN_CONFIG['premium_price_per_day']
            line += f"Цена: {price} токенов за 1 день\n"
        
        line += f"ID: `{model_id}`"
        result.append(line)
    
    return "\n\n".join(result)


def can_user_access_model(model_id: str, user_premium_expires: Optional[datetime]) -> bool:
    """
    Проверить, может ли пользователь использовать модель
    
    Args:
        model_id: ID модели
        user_premium_expires: Дата истечения премиум доступа пользователя
    
    Returns:
        True если доступ есть
    """
    config = get_model_config(model_id)
    if not config:
        return False
    
    # Бесплатные модели доступны всем
    if config.tier == ModelTier.FREE:
        return True
    
    # Премиум модели требуют активной подписки
    if user_premium_expires is None:
        return False
    
    return datetime.now() < user_premium_expires


def validate_model_access(model_id: str, user_premium_expires: Optional[datetime]) -> tuple[bool, str]:
    """
    Валидировать доступ к модели и вернуть сообщение об ошибке
    
    Returns:
        (success, error_message)
    """
    from constants import TOKEN_CONFIG
    
    config = get_model_config(model_id)
    
    if not config:
        return False, f"Модель '{model_id}' не найдена ❌"
    
    if not can_user_access_model(model_id, user_premium_expires):
        price = TOKEN_CONFIG['premium_price_per_day']
        # Escape model name for Markdown
        escaped_name = escape_markdown(config.name)
        return False, (
            f"У вас нет доступа к модели *{escaped_name}* ❌\n\n"
            f"Эта модель доступна только с премиум подпиской.\n"
            f"Цена: {price} токенов/день 💰\n\n"
            f"Используйте /buy\\_premium чтобы купить доступ."
        )
    
    return True, ""
