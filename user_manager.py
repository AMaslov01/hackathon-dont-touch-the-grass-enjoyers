"""
User Manager for handling user accounts and token operations
"""
import logging
import json
from datetime import datetime, timedelta
from typing import Optional
from database import user_repo
from constants import TOKEN_CONFIG, TIME_FORMAT

logger = logging.getLogger(__name__)


class UserManager:
    """Manages user operations and token system"""
    
    def __init__(self):
        self.cost_per_request = TOKEN_CONFIG['cost_per_request']
    
    def get_or_create_user(self, user_id: int, username: str = None,
                          first_name: str = None, last_name: str = None) -> dict:
        """
        Get existing user or create new one
        
        Args:
            user_id: Telegram user ID
            username: Telegram username
            first_name: User's first name
            last_name: User's last name
            
        Returns:
            User dictionary with all information
        """
        return user_repo.get_or_create_user(user_id, username, first_name, last_name)
    
    def check_and_refresh_tokens(self, user_id: int) -> dict:
        """
        Check if user needs token refresh and refresh if needed
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Updated user dictionary
        """
        return user_repo.refresh_tokens(user_id)
    
    def has_enough_tokens(self, user_id: int, required_tokens: int = None) -> bool:
        """
        Check if user has enough tokens
        
        Args:
            user_id: Telegram user ID
            required_tokens: Number of tokens required (default: cost_per_request)
            
        Returns:
            True if user has enough tokens, False otherwise
        """
        if required_tokens is None:
            required_tokens = self.cost_per_request
        
        user = user_repo.get_user(user_id)
        return user and user['tokens'] >= required_tokens
    
    def use_tokens(self, user_id: int, amount: int = None) -> bool:
        """
        Deduct tokens from user account
        
        Args:
            user_id: Telegram user ID
            amount: Number of tokens to deduct (default: cost_per_request)
            
        Returns:
            True if successful, False if not enough tokens
        """
        if amount is None:
            amount = self.cost_per_request
        
        return user_repo.use_tokens(user_id, amount)
    
    def get_balance_info(self, user_id: int) -> dict:
        """
        Get user's token balance and refresh time
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Dictionary with balance information
        """
        user = user_repo.get_user(user_id)
        if not user:
            return None
        
        # Calculate next refresh time
        last_refresh = user['last_token_refresh']
        next_refresh = last_refresh + timedelta(hours=TOKEN_CONFIG['refresh_interval_hours'])
        
        return {
            'tokens': user['tokens'],
            'max_tokens': user['max_tokens'],
            'last_refresh': last_refresh.strftime(TIME_FORMAT),
            'next_refresh': next_refresh.strftime(TIME_FORMAT),
            'refresh_available': datetime.now() >= next_refresh
        }
    
    def log_usage(self, user_id: int, prompt: str, response: str, 
                  tokens_used: int = None):
        """
        Log usage to history
        
        Args:
            user_id: Telegram user ID
            prompt: User's prompt
            response: AI response
            tokens_used: Number of tokens used (default: cost_per_request)
        """
        if tokens_used is None:
            tokens_used = self.cost_per_request
        
        try:
            user_repo.add_usage_history(user_id, prompt, response, tokens_used)
        except Exception as e:
            logger.error(f"Failed to log usage for user {user_id}: {e}")
    
    def process_request(self, user_id: int, tokens_amount: int = None) -> tuple[bool, Optional[str]]:
        """
        Process a user request (check tokens and deduct if available)
        
        Args:
            user_id: Telegram user ID
            tokens_amount: Number of tokens required (default: cost_per_request)
            
        Returns:
            Tuple of (success, error_message)
            success: True if request can proceed
            error_message: Error message if request cannot proceed
        """
        if tokens_amount is None:
            tokens_amount = self.cost_per_request
        
        # Refresh tokens if needed
        self.check_and_refresh_tokens(user_id)
        
        # Check if user has enough tokens
        if not self.has_enough_tokens(user_id, tokens_amount):
            balance = self.get_balance_info(user_id)
            return False, balance['next_refresh']
        
        # Deduct tokens
        if not self.use_tokens(user_id, tokens_amount):
            return False, "Не удалось списать токены"
        
        return True, None
    
    def get_business_info(self, user_id: int) -> Optional[dict]:
        """
        Get user's business information
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Dictionary with business information or None
        """
        info_json = user_repo.get_business_info(user_id)
        if info_json:
            try:
                return json.loads(info_json)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse business info for user {user_id}")
                return None
        return None
    
    def save_business_info(self, user_id: int, business_type: str, 
                          financial_situation: str, goals: str) -> bool:
        """
        Save user's business information
        
        Args:
            user_id: Telegram user ID
            business_type: Description of business type and audience
            financial_situation: Current financial situation
            goals: Business goals and challenges
            
        Returns:
            True if saved successfully, False otherwise
        """
        business_info = {
            'business_type': business_type,
            'financial_situation': financial_situation,
            'goals': goals,
            'updated_at': datetime.now().isoformat()
        }
        
        try:
            info_json = json.dumps(business_info, ensure_ascii=False)
            return user_repo.save_business_info(user_id, info_json)
        except Exception as e:
            logger.error(f"Failed to save business info for user {user_id}: {e}")
            return False
    
    def has_business_info(self, user_id: int) -> bool:
        """
        Check if user has saved business information
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if user has business info, False otherwise
        """
        return self.get_business_info(user_id) is not None
    
    def get_workers_info(self, user_id: int) -> Optional[dict]:
        """
        Get user's workers search information
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Dictionary with workers search information or None
        """
        info_json = user_repo.get_workers_info(user_id)
        if info_json:
            try:
                return json.loads(info_json)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse workers info for user {user_id}")
                return None
        return None
    
    def save_workers_info(self, user_id: int, description: str) -> bool:
        """
        Save user's workers search information
        
        Args:
            user_id: Telegram user ID
            description: Description of needed workers/employees
            
        Returns:
            True if saved successfully, False otherwise
        """
        workers_info = {
            'description': description,
            'updated_at': datetime.now().isoformat()
        }
        
        try:
            info_json = json.dumps(workers_info, ensure_ascii=False)
            return user_repo.save_workers_info(user_id, info_json)
        except Exception as e:
            logger.error(f"Failed to save workers info for user {user_id}: {e}")
            return False
    
    def has_workers_info(self, user_id: int) -> bool:
        """
        Check if user has saved workers search information
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if user has workers info, False otherwise
        """
        return self.get_workers_info(user_id) is not None
    
    def get_executors_info(self, user_id: int) -> Optional[dict]:
        """
        Get user's executors search information
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Dictionary with executors search information or None
        """
        info_json = user_repo.get_executors_info(user_id)
        if info_json:
            try:
                return json.loads(info_json)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse executors info for user {user_id}")
                return None
        return None
    
    def save_executors_info(self, user_id: int, description: str) -> bool:
        """
        Save user's executors search information
        
        Args:
            user_id: Telegram user ID
            description: Description of needed executors/freelancers
            
        Returns:
            True if saved successfully, False otherwise
        """
        executors_info = {
            'description': description,
            'updated_at': datetime.now().isoformat()
        }
        
        try:
            info_json = json.dumps(executors_info, ensure_ascii=False)
            return user_repo.save_executors_info(user_id, info_json)
        except Exception as e:
            logger.error(f"Failed to save executors info for user {user_id}: {e}")
            return False
    
    def has_executors_info(self, user_id: int) -> bool:
        """
        Check if user has saved executors search information
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if user has executors info, False otherwise
        """
        return self.get_executors_info(user_id) is not None


# Global user manager instance
user_manager = UserManager()

