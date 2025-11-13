"""
User Manager for handling user accounts and token operations
"""
import logging
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
    
    def process_request(self, user_id: int) -> tuple[bool, Optional[str]]:
        """
        Process a user request (check tokens and deduct if available)
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Tuple of (success, error_message)
            success: True if request can proceed
            error_message: Error message if request cannot proceed
        """
        # Refresh tokens if needed
        self.check_and_refresh_tokens(user_id)
        
        # Check if user has enough tokens
        if not self.has_enough_tokens(user_id):
            balance = self.get_balance_info(user_id)
            return False, balance['next_refresh']
        
        # Deduct tokens
        if not self.use_tokens(user_id):
            return False, "Не удалось списать токены"
        
        return True, None


# Global user manager instance
user_manager = UserManager()

