"""
AI Client for interacting with OpenRouter API
"""
import logging
import requests
from typing import Optional
from config import Config

logger = logging.getLogger(__name__)


class AIClient:
    """Client for AI API interactions"""
    
    def __init__(self):
        self.api_url = Config.OPENROUTER_API_URL
        self.api_key = Config.OPENROUTER_API_KEY
        self.model = Config.AI_MODEL
        
        # System prompt to make responses in Russian
        self.system_prompt = (
            "Ты полезный AI-ассистент. "
            "Всегда отвечай на русском языке. "
            "Будь вежливым, кратким и полезным."
            "Доступные команды: /start, /balance, /finance, /help"
        )
    
    def generate_response(self, user_prompt: str, system_prompt: str = None) -> str:
        """
        Generate AI response for user prompt
        
        Args:
            user_prompt: User's question or request
            system_prompt: Optional custom system prompt (uses default if not provided)
            
        Returns:
            AI generated response in Russian
            
        Raises:
            Exception: If API call fails
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        data = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt or self.system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
        }
        
        try:
            logger.info(f"Sending request to AI API with model: {self.model}")
            response = requests.post(
                self.api_url, 
                headers=headers, 
                json=data, 
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()
            ai_response = result['choices'][0]['message']['content']
            
            logger.info(f"Successfully received AI response (length: {len(ai_response)})")
            return ai_response
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"AI API HTTP error: {e}")
            logger.error(f"Response status: {response.status_code}")
            logger.error(f"Response body: {response.text[:500]}")
            raise Exception(f"AI API error: {response.status_code}")
            
        except requests.exceptions.Timeout:
            logger.error("AI API request timeout")
            raise Exception("AI API timeout")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"AI API request failed: {e}")
            raise Exception("AI API connection error")
            
        except (KeyError, IndexError) as e:
            logger.error(f"Failed to parse AI response: {e}")
            logger.error(f"Response: {response.text[:500]}")
            raise Exception("Invalid AI response format")
        
        except Exception as e:
            logger.error(f"Unexpected error in AI client: {e}")
            raise
    
    def generate_financial_plan(self, business_info: dict) -> str:
        """
        Generate detailed financial plan based on business information
        
        Args:
            business_info: Dictionary with business information
                - business_type: Business type and audience description
                - financial_situation: Current financial situation
                - goals: Business goals and challenges
        
        Returns:
            Detailed financial plan in Russian, formatted for PDF generation
            
        Raises:
            Exception: If API call fails
        """
        system_prompt = (
            "Ты опытный финансовый консультант и бизнес-аналитик. "
            "Твоя задача - составлять подробные, практичные и персонализированные финансовые планы для бизнеса. "
            "Твои рекомендации должны быть:\n"
            "1. Конкретными и реализуемыми\n"
            "2. Основанными на предоставленной информации\n"
            "3. Структурированными с использованием заголовков в формате Markdown (# Заголовок)\n"
            "4. Содержать конкретные цифры и сроки где это возможно\n"
            "5. Включать анализ рисков и возможностей\n\n"
            "ВАЖНО: Используй структуру с заголовками:\n"
            "- Используй # для основных разделов (например, # Анализ текущей ситуации)\n"
            "- Используй маркированные списки (-, *) для перечислений\n"
            "- Используй **жирный текст** для выделения важных моментов\n"
            "- Для вложенных списков добавляй отступы (два пробела перед маркером)\n"
            "- Используй таблицы в формате Markdown для финансовых данных:\n"
            "  | Показатель | Значение |\n"
            "  |------------|----------|\n"
            "  | Доходы     | 100000   |\n\n"
            "СТРОГО ЗАПРЕЩЕНО использовать эмодзи или специальные символы (смайлики, иконки и т.д.)!\n"
            "Отвечай на русском языке. Твой ответ будет конвертирован в красивый PDF документ."
        )
        
        user_prompt = f"""
На основе следующей информации о бизнесе составь подробный финансовый план:

**Информация о бизнесе:**
{business_info.get('business_type', 'Не указана')}

**Текущая финансовая ситуация:**
{business_info.get('financial_situation', 'Не указана')}

**Цели и задачи:**
{business_info.get('goals', 'Не указаны')}

Составь подробный финансовый план со следующими разделами (используй # для заголовков):

# 1. Анализ текущей ситуации
- Оцени сильные и слабые стороны бизнеса
- Проанализируй финансовое состояние
- Выяви ключевые возможности и угрозы

# 2. Рекомендации по оптимизации расходов
- Конкретные шаги для снижения затрат
- Приоритизация расходов
- Потенциальная экономия

# 3. Стратегии увеличения доходов
- Новые источники дохода
- Оптимизация ценообразования
- Расширение клиентской базы

# 4. План действий
- Конкретные шаги с указанием сроков
- Ключевые показатели эффективности (KPI)
- Ресурсы, необходимые для реализации

# 5. Финансовый прогноз
Создай таблицу с прогнозом на 3-6 месяцев в формате:
| Месяц | Доходы (руб) | Расходы (руб) | Прибыль (руб) |
|-------|--------------|---------------|---------------|
| 1     | ...          | ...           | ...           |

# 6. Управление рисками
- Основные риски и их вероятность
- Стратегии минимизации рисков
- План действий в кризисных ситуациях

Будь конкретным, используй числа и примеры, основанные на предоставленной информации.
"""
        
        return self.generate_response(user_prompt, system_prompt)


# Global AI client instance
ai_client = AIClient()

