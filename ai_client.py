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
        )
    
    def generate_response(self, user_prompt: str) -> str:
        """
        Generate AI response for user prompt
        
        Args:
            user_prompt: User's question or request
            
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
                    "content": self.system_prompt
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
                timeout=30
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


# Global AI client instance
ai_client = AIClient()

