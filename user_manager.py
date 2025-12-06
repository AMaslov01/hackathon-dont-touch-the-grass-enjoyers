"""
User Manager for handling user accounts and token operations
"""
import logging
import json
from datetime import datetime, timedelta
from typing import Optional
from database import user_repo, business_repo
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
        business = business_repo.get_business(user_id)
        if business:
            return {
                'business_name': business.get('business_name'),
                'business_type': business.get('business_type'),
                'financial_situation': business.get('financial_situation'),
                'goals': business.get('goals')
            }
        return None

    def save_business_info(self, user_id: int, business_name: str, business_type: str,
                           financial_situation: str, goals: str) -> bool:
        """
        Save user's business information
        
        Args:
            user_id: Telegram user ID
            business_name: Business name
            business_type: Description of business type and audience
            financial_situation: Current financial situation
            goals: Business goals and challenges
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            business_repo.create_business(
                owner_id=user_id,
                business_name=business_name,
                business_type=business_type,
                financial_situation=financial_situation,
                goals=goals
            )
            return True
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
        return business_repo.is_business_owner(user_id)

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

    def get_user_info(self, user_id: int) -> Optional[str]:
        """
        Get user's personal description
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            User info string or None
        """
        return user_repo.get_user_info(user_id)

    def save_user_info(self, user_id: int, user_info: str) -> bool:
        """
        Save user's personal description
        
        Args:
            user_id: Telegram user ID
            user_info: User's personal description
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            return user_repo.save_user_info(user_id, user_info)
        except Exception as e:
            logger.error(f"Failed to save user info for user {user_id}: {e}")
            return False

    def has_user_info(self, user_id: int) -> bool:
        """
        Check if user has filled their personal description
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if user has info, False otherwise
        """
        info = self.get_user_info(user_id)
        return info is not None and len(info.strip()) > 0

    def get_users_without_business_or_job(self, exclude_user_id: int = None) -> list:
        """
        Get users who are not business owners and not currently employed
        
        Args:
            exclude_user_id: User ID to exclude from results
            
        Returns:
            List of user dictionaries with user_id, username, first_name, user_info, overall_rating
        """
        return user_repo.get_users_without_business_or_job(exclude_user_id)

    # Business and employee management methods

    def get_business(self, user_id: int) -> Optional[dict]:
        """Get active business owned by user"""
        return business_repo.get_active_business(user_id)
    
    def get_active_business(self, user_id: int) -> Optional[dict]:
        """Get active business for user"""
        return business_repo.get_active_business(user_id)
    
    def get_all_user_businesses(self, user_id: int) -> list:
        """Get all businesses owned by user"""
        return business_repo.get_all_user_businesses(user_id)
    
    def set_active_business(self, user_id: int, business_id: int) -> tuple[bool, str]:
        """
        Set active business for user
        
        Args:
            user_id: User ID
            business_id: Business ID to set as active
            
        Returns:
            Tuple of (success, message)
        """
        success = business_repo.set_active_business(user_id, business_id)
        if success:
            return True, "Активный бизнес успешно изменен"
        else:
            return False, "Не удалось изменить активный бизнес. Возможно, он вам не принадлежит."
    
    def delete_business(self, user_id: int, business_id: int) -> tuple[bool, str]:
        """
        Delete business with cascade deletion
        
        Args:
            user_id: User ID
            business_id: Business ID to delete
            
        Returns:
            Tuple of (success, message)
        """
        # Check that user has more than one business or confirm deletion of last one
        businesses = self.get_all_user_businesses(user_id)
        
        if not any(b['id'] == business_id for b in businesses):
            return False, "Бизнес не найден или не принадлежит вам"
        
        success = business_repo.delete_business(user_id, business_id)
        if success:
            remaining = len(businesses) - 1
            if remaining > 0:
                return True, f"Бизнес удален. У вас осталось бизнесов: {remaining}"
            else:
                return True, "Бизнес удален. У вас больше нет бизнесов."
        else:
            return False, "Не удалось удалить бизнес"

    def is_business_owner(self, user_id: int) -> bool:
        """Check if user is a business owner (has at least one business)"""
        return business_repo.is_business_owner(user_id)
    
    def has_active_business(self, user_id: int) -> bool:
        """Check if user has an active business"""
        return business_repo.has_active_business(user_id)

    def is_employee(self, user_id: int, business_id: int = None) -> bool:
        """Check if user is an employee"""
        return business_repo.is_employee(user_id, business_id)

    def get_user_by_username(self, username: str) -> Optional[int]:
        """Get user_id by username"""
        return business_repo.get_user_by_username(username)

    def invite_employee(self, owner_id: int, target_username: str) -> tuple[bool, str]:
        """
        Invite an employee to active business
        
        Args:
            owner_id: Business owner user ID
            target_username: Username of user to invite
            
        Returns:
            Tuple of (success, message)
        """
        # Check if owner has an active business
        business = business_repo.get_active_business(owner_id)
        if not business:
            return False, "У вас нет активного бизнеса. Сначала создайте бизнес через /create_business"

        # Find target user
        target_user_id = business_repo.get_user_by_username(target_username)
        if not target_user_id:
            return False, f"Пользователь @{target_username} не найден или не использует бота"

        # Check if trying to invite yourself
        if target_user_id == owner_id:
            return False, "Вы не можете пригласить самого себя"

        # Send invitation
        success = business_repo.invite_employee(business['id'], target_user_id)
        if success:
            return True, f"Приглашение отправлено пользователю @{target_username}"
        else:
            return False, f"Приглашение уже было отправлено пользователю @{target_username}"

    def get_pending_invitations(self, user_id: int) -> list:
        """Get pending invitations for user"""
        return business_repo.get_pending_invitations(user_id)

    def respond_to_invitation(self, invitation_id: int, accept: bool) -> bool:
        """Accept or reject an invitation"""
        return business_repo.respond_to_invitation(invitation_id, accept)

    def get_employees(self, business_id: int, status: str = 'accepted') -> list:
        """Get employees of a business"""
        return business_repo.get_employees(business_id, status)

    def get_all_employees(self, business_id: int) -> list:
        """Get all employees of a business (all statuses)"""
        return business_repo.get_all_employees(business_id)

    def get_user_businesses(self, user_id: int) -> list:
        """Get businesses where user is an employee"""
        return business_repo.get_user_businesses(user_id)

    def remove_employee(self, owner_id: int, employee_user_id: int) -> tuple[bool, str]:
        """
        Remove an employee from active business
        
        Args:
            owner_id: Business owner user ID
            employee_user_id: Employee user ID to remove
            
        Returns:
            Tuple of (success, message)
        """
        business = business_repo.get_active_business(owner_id)
        if not business:
            return False, "У вас нет активного бизнеса"

        success = business_repo.remove_employee(business['id'], employee_user_id)
        if success:
            return True, "Сотрудник удален из вашего бизнеса"
        else:
            return False, "Не удалось удалить сотрудника (возможно, он не является вашим сотрудником)"

    # Task management methods

    def create_task_with_ai_recommendation(self, owner_id: int, title: str,
                                           description: str, deadline_minutes: int = None,
                                           difficulty: int = None, priority: str = None) -> tuple[bool, str, Optional[dict]]:
        """
        Create a task and get AI recommendation for best employee
        
        Args:
            owner_id: Business owner user ID
            title: Task title
            description: Task description
            deadline_minutes: Deadline in minutes
            difficulty: Task difficulty (1-5)
            priority: Task priority (низкий, средний, высокий)
            
        Returns:
            Tuple of (success, message, task_dict or None)
        """
        from ai_client import ai_client

        # Check if user has active business
        business = business_repo.get_active_business(owner_id)
        if not business:
            return False, "У вас нет активного бизнеса", None

        # Get employees task history
        employees_history = business_repo.get_all_employees_task_history(business['id'])

        # Get AI recommendation
        ai_recommendation = None
        recommended_employee_id = None

        if employees_history:
            try:
                ai_recommendation = ai_client.recommend_employee_for_task(
                    title, description, employees_history
                )
                if ai_recommendation:
                    recommended_employee_id = ai_recommendation.get('user_id')
            except Exception as e:
                logger.error(f"Failed to get AI recommendation: {e}")

        # Create task
        try:
            task = business_repo.create_task(
                business_id=business['id'],
                title=title,
                description=description,
                created_by=owner_id,
                deadline_minutes=deadline_minutes,
                difficulty=difficulty,
                priority=priority,
                ai_recommended_employee=recommended_employee_id
            )
            return True, "Задача создана", {
                'task': task,
                'ai_recommendation': ai_recommendation
            }
        except Exception as e:
            logger.error(f"Failed to create task: {e}")
            return False, "Не удалось создать задачу", None

    def get_available_tasks_for_employee(self, user_id: int) -> list:
        """Get available tasks for employee's businesses"""
        businesses = business_repo.get_user_businesses(user_id)
        all_tasks = []
        for business in businesses:
            tasks = business_repo.get_available_tasks(business['id'])
            for task in tasks:
                task['business_name'] = business['business_name']
            all_tasks.extend(tasks)
        return all_tasks

    def get_my_tasks(self, user_id: int) -> list:
        """Get user's assigned tasks"""
        return business_repo.get_assigned_tasks(user_id)

    def take_task(self, user_id: int, task_id: int) -> tuple[bool, str]:
        """Employee takes a task"""
        # Check if task exists and is available
        task = business_repo.get_task(task_id)
        if not task:
            return False, "Задача не найдена"

        if task['status'] != 'available':
            return False, "Задача уже назначена или выполнена"

        # Check if user is employee of this business
        if not business_repo.is_employee(user_id, task['business_id']):
            return False, "Вы не являетесь сотрудником этого бизнеса"

        # Take task
        success = business_repo.take_task(task_id, user_id)
        if success:
            return True, "Вы взяли задачу!"
        else:
            return False, "Не удалось взять задачу"

    def assign_task_to_employee(self, owner_id: int, task_id: int,
                                employee_user_id: int) -> tuple[bool, str]:
        """Owner assigns task to specific employee"""
        # Check if owner has active business
        business = business_repo.get_active_business(owner_id)
        if not business:
            return False, "У вас нет активного бизнеса"

        # Check if task belongs to this business
        task = business_repo.get_task(task_id)
        if not task:
            return False, "Задача не найдена"

        if task['business_id'] != business['id']:
            return False, "Эта задача не принадлежит вашему бизнесу"

        if task['status'] not in ('available', 'abandoned'):
            return False, "Задача уже назначена или выполнена"

        # Check if target is employee
        if not business_repo.is_employee(employee_user_id, business['id']):
            return False, "Этот пользователь не является вашим сотрудником"

        # Assign task
        success = business_repo.assign_task(task_id, employee_user_id, owner_id)
        if success:
            if task['status'] == 'abandoned':
                abandoned_by = None
                if task.get('abandoned_by'):
                    user = user_repo.get_user(task['abandoned_by'])
                    abandoned_by = f"@{user['username']}" if user and user.get(
                        'username') else f"ID {task['abandoned_by']}"
                message = "Задача назначена сотруднику (ранее была отказана"
                if abandoned_by:
                    message += f" {abandoned_by}"
                message += ")"
                return True, message
            else:
                return True, "Задача назначена сотруднику"
        else:
            return False, "Не удалось назначить задачу"

    def assign_task_to_employee_by_username(self, owner_id: int, task_id: int,
                                            employee_username: str) -> tuple[bool, str, Optional[int]]:
        """Owner assigns task to employee by username"""
        # Find employee by username
        employee_user_id = business_repo.get_user_by_username(employee_username)
        if not employee_user_id:
            return False, f"Пользователь @{employee_username} не найден или не использует бота", None

        # Use existing method
        success, message = self.assign_task_to_employee(owner_id, task_id, employee_user_id)
        return success, message, employee_user_id if success else None

    def complete_task(self, user_id: int, task_id: int) -> tuple[bool, str]:
        """Employee submits a task for review"""
        success = business_repo.complete_task(task_id, user_id)
        if success:
            return True, "Задача отправлена на проверку работодателю!"
        else:
            return False, "Не удалось отправить задачу. Возможно, она не назначена вам."

    def get_business_all_tasks(self, owner_id: int) -> list:
        """Owner gets all tasks of their active business"""
        business = business_repo.get_active_business(owner_id)
        if not business:
            return []
        return business_repo.get_business_tasks(business['id'])

    def abandon_task(self, user_id: int, task_id: int) -> tuple[bool, str]:
        """Employee abandons a task they've taken"""
        task = business_repo.get_task(task_id)
        if not task:
            return False, "Задача не найдена"

        if task['assigned_to'] != user_id:
            return False, "Эта задача не назначена вам"

        if task['status'] not in ('assigned', 'in_progress'):
            return False, "Нельзя отказаться от задачи с текущим статусом"

        success = business_repo.abandon_task(task_id, user_id)
        if success:
            # Log abandonment to usage history
            # self.log_usage( Пока убрал, т.к usage history у нас сейчас хранит лишь promt'ы и ответы AI, а не все запросы и ответы пользователя
            # TODO: возможно, стоит вернуть этот метод обратно, если будет реализован хранение всех запросов и ответов пользователя
            #     user_id,
            #     f"Отказ от задачи #{task_id}: {task['title']}",
            #     f"Пользователь отказался от выполнения задачи. Описание: {task.get('description', 'Нет описания')}",
            #     tokens_used=0  # No tokens spent on abandonment
            # )
            return True, "Вы отказались от задачи. Задача переведена в статус 'отказана'."
        else:
            return False, "Не удалось отказаться от задачи"
    
    # Task review methods (for business owners)
    
    def get_submitted_tasks(self, owner_id: int) -> list:
        """Get all tasks submitted for review"""
        business = business_repo.get_active_business(owner_id)
        if not business:
            return []
        return business_repo.get_submitted_tasks(business['id'])
    
    def accept_task(self, owner_id: int, task_id: int, quality_coefficient: float) -> tuple[bool, str, Optional[dict]]:
        """
        Accept submitted task with quality rating
        
        Args:
            owner_id: Business owner user ID
            task_id: Task ID
            quality_coefficient: Quality rating from 0.5 to 1.0
            
        Returns:
            Tuple of (success, message, result_dict)
        """
        # Validate quality coefficient
        if not (0.5 <= quality_coefficient <= 1.0):
            return False, "Коэффициент качества должен быть от 0.5 до 1.0", None
        
        # Check if user has active business
        business = business_repo.get_active_business(owner_id)
        if not business:
            return False, "У вас нет активного бизнеса", None
        
        # Check if task belongs to this business
        task = business_repo.get_task(task_id)
        if not task:
            return False, "Задача не найдена", None
        
        if task['business_id'] != business['id']:
            return False, "Эта задача не принадлежит вашему активному бизнесу", None
        
        if task['status'] != 'submitted':
            return False, "Задача не отправлена на проверку", None
        
        # Accept task
        result = business_repo.accept_task(task_id, quality_coefficient, business['id'])
        if result:
            employee_username = task.get('assigned_to_username')
            if employee_username:
                employee_name = f"@{employee_username}"
            else:
                employee_name = task.get('assigned_to_name', f"ID {result['employee_id']}")
            return True, (
                f"Задача принята!\n"
                f"Сотрудник: {employee_name}\n"
                f"Изменение рейтинга: +{result['rating_change']}\n"
                f"Новый рейтинг: {result['new_rating']}"
            ), result
        else:
            return False, "Не удалось принять задачу", None
    
    def reject_task(self, owner_id: int, task_id: int) -> tuple[bool, str]:
        """
        Reject submitted task and apply rating penalty
        
        Args:
            owner_id: Business owner user ID
            task_id: Task ID
            
        Returns:
            Tuple of (success, message)
        """
        # Check if user has active business
        business = business_repo.get_active_business(owner_id)
        if not business:
            return False, "У вас нет активного бизнеса"
        
        # Check if task belongs to this business
        task = business_repo.get_task(task_id)
        if not task:
            return False, "Задача не найдена"
        
        if task['business_id'] != business['id']:
            return False, "Эта задача не принадлежит вашему активному бизнесу"
        
        if task['status'] != 'submitted':
            return False, "Задача не отправлена на проверку"
        
        # Reject task
        success = business_repo.reject_task(task_id, business['id'])
        if success:
            employee_username = task.get('assigned_to_username')
            if employee_username:
                employee_name = f"@{employee_username}"
            else:
                employee_name = task.get('assigned_to_name', f"ID {task['assigned_to']}")
            return True, f"Задача отклонена. Сотрудник {employee_name} получил штраф -20 рейтинга. Задача возвращена в пул."
        else:
            return False, "Не удалось отклонить задачу"
    
    def send_task_for_revision(self, owner_id: int, task_id: int, new_deadline_minutes: int) -> tuple[bool, str]:
        """
        Send task back for revision with new deadline
        
        Args:
            owner_id: Business owner user ID
            task_id: Task ID
            new_deadline_minutes: New deadline in minutes
            
        Returns:
            Tuple of (success, message)
        """
        if new_deadline_minutes <= 0:
            return False, "Дедлайн должен быть положительным числом"
        
        # Check if user has active business
        business = business_repo.get_active_business(owner_id)
        if not business:
            return False, "У вас нет активного бизнеса"
        
        # Check if task belongs to this business
        task = business_repo.get_task(task_id)
        if not task:
            return False, "Задача не найдена"
        
        if task['business_id'] != business['id']:
            return False, "Эта задача не принадлежит вашему активному бизнесу"
        
        if task['status'] != 'submitted':
            return False, "Задача не отправлена на проверку"
        
        # Send for revision
        success = business_repo.send_for_revision(task_id, new_deadline_minutes, business['id'])
        if success:
            employee_username = task.get('assigned_to_username')
            if employee_username:
                employee_name = f"@{employee_username}"
            else:
                employee_name = task.get('assigned_to_name', f"ID {task['assigned_to']}")
            # Convert minutes to hours for display
            new_deadline_hours = new_deadline_minutes / 60
            return True, f"Задача отправлена на доработку сотруднику {employee_name}. Новый дедлайн: {new_deadline_hours:.1f} ч."
        else:
            return False, "Не удалось отправить задачу на доработку"
    
    def get_employee_rating(self, owner_id: int, employee_user_id: int) -> Optional[int]:
        """Get employee rating in owner's active business"""
        business = business_repo.get_active_business(owner_id)
        if not business:
            return None
        return business_repo.get_employee_rating(business['id'], employee_user_id)

    # Roulette methods
    
    def spin_roulette(self, user_id: int) -> tuple[bool, str, Optional[dict]]:
        """
        Spin the roulette and get random tokens
        
        Returns:
            Tuple of (success, message, result_dict)
            result_dict contains: amount, new_balance, next_spin
        """
        import random
        from constants import TOKEN_CONFIG
        
        # Check if user can spin
        can_spin, next_spin = user_repo.can_spin_roulette(user_id)
        
        if not can_spin:
            # Format next spin time
            time_left = next_spin - datetime.now()
            hours_left = int(time_left.total_seconds() // 3600)
            minutes_left = int((time_left.total_seconds() % 3600) // 60)
            
            if hours_left > 0:
                time_str = f"{hours_left} ч {minutes_left} мин"
            else:
                time_str = f"{minutes_left} мин"
            
            user = user_repo.get_user(user_id)
            return False, f"Рулетка будет доступна через {time_str}", {
                'tokens': user['tokens'] if user else 0,
                'next_spin': next_spin.strftime(TIME_FORMAT)
            }
        
        # Spin the roulette
        min_amount = TOKEN_CONFIG['roulette_min']
        max_amount = TOKEN_CONFIG['roulette_max']
        amount = random.randint(min_amount, max_amount)
        
        # Give tokens to user
        success = user_repo.spin_roulette(user_id, amount)
        
        if success:
            user = user_repo.get_user(user_id)
            next_spin_time = datetime.now() + timedelta(hours=TOKEN_CONFIG['roulette_interval_hours'])
            
            return True, f"Вы выиграли {amount} токенов!", {
                'amount': amount,
                'new_balance': user['tokens'] if user else amount,
                'next_spin': next_spin_time.strftime(TIME_FORMAT)
            }
        else:
            return False, "Ошибка при вращении рулетки", None
    
    def check_and_notify_roulette(self, user_id: int) -> bool:
        """
        Check if user needs to be notified about available roulette
        
        Returns:
            True if notification is needed, False otherwise
        """
        return user_repo.check_roulette_notification_needed(user_id)
    
    def mark_roulette_notified(self, user_id: int) -> bool:
        """Mark that user has been notified about roulette"""
        return user_repo.mark_roulette_notified(user_id)

    # Model management methods

    def get_user_model(self, user_id: int) -> str:
        """
        Get user's selected AI model
        
        Args:
            user_id: Telegram user ID
        
        Returns:
            Model ID (defaults to 'llama3-finance' if not set)
        """
        try:
            model_id = user_repo.get_user_model(user_id)
            return model_id if model_id else 'llama3-finance'
        except Exception as e:
            logger.error(f"Failed to get user model for {user_id}: {e}")
            return 'llama3-finance'

    def set_user_model(self, user_id: int, model_id: str) -> bool:
        """
        Set user's AI model
        
        Args:
            user_id: Telegram user ID
            model_id: Model ID to set
        
        Returns:
            True if successful
        """
        try:
            return user_repo.set_user_model(user_id, model_id)
        except Exception as e:
            logger.error(f"Failed to set user model for {user_id}: {e}")
            return False

    def get_user_premium_expires(self, user_id: int) -> Optional[datetime]:
        """
        Get user's premium expiration date
        
        Args:
            user_id: Telegram user ID
        
        Returns:
            Premium expiration datetime or None
        """
        try:
            return user_repo.get_user_premium_expires(user_id)
        except Exception as e:
            logger.error(f"Failed to get premium expires for {user_id}: {e}")
            return None

    def purchase_premium(self, user_id: int, days: int = 1) -> tuple[bool, str]:
        """
        Purchase premium access for specified days
        
        Args:
            user_id: Telegram user ID
            days: Number of days to purchase (default: 1)
        
        Returns:
            Tuple of (success, message)
        """
        PREMIUM_PRICE_PER_DAY = TOKEN_CONFIG['premium_price_per_day']

        try:
            # Check balance
            user = user_repo.get_user(user_id)
            if not user:
                return False, "Пользователь не найден"

            total_cost = PREMIUM_PRICE_PER_DAY * days
            if user['tokens'] < total_cost:
                return False, f"Недостаточно токенов. Нужно: {total_cost}, у вас: {user['tokens']}"

            # Calculate new expiration date
            current_expires = self.get_user_premium_expires(user_id)
            now = datetime.now()

            if current_expires and current_expires > now:
                # Extend existing subscription
                new_expires = current_expires + timedelta(days=days)
            else:
                # New subscription
                new_expires = now + timedelta(days=days)

            # Deduct tokens and set premium
            success = user_repo.purchase_premium(user_id, total_cost, new_expires)

            if success:
                return True, f"Премиум доступ активирован на {days} дн."
            else:
                return False, "Не удалось активировать премиум доступ"

        except Exception as e:
            logger.error(f"Failed to purchase premium for {user_id}: {e}")
            return False, "Произошла ошибка при покупке премиум доступа"


# Global user manager instance
user_manager = UserManager()
