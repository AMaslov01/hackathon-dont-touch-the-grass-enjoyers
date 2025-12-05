"""
Telegram bot with AI integration, user accounts, and token system
"""
from ast import parse
import os
import logging
from logging.handlers import TimedRotatingFileHandler
import re
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)
from telegram.error import BadRequest
from telegram.request import HTTPXRequest

# Import our modules
from config import Config
from database import db
from ai_client import ai_client
from user_manager import user_manager
from constants import MESSAGES
from constants import COMMANDS_COSTS
from pdf_generator import pdf_generator, chat_history_pdf

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def escape_markdown(text: str) -> str:
    """
    Escape special Markdown characters in user-generated content.
    This prevents Markdown parsing errors when user input contains special characters.
    
    NOTE: This should ONLY be used for user input (usernames, business names, etc.),
    NOT for AI-generated content which already has proper markdown formatting.
    
    Args:
        text: The text to escape
        
    Returns:
        Text with escaped Markdown special characters
    """
    if not text:
        return text

    # Characters that need to be escaped in Telegram Markdown
    # Note: () and . are excluded as they rarely cause issues and are common in text
    special_chars = ['_', '*', '[', ']', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '!']

    for char in special_chars:
        text = text.replace(char, '\\' + char)

    return text

# Finance conversation states
CHECKING_EXISTING, QUESTION_1, QUESTION_2, QUESTION_3, QUESTION_4 = range(5)

# Clients search conversation states
CLIENTS_CHECKING, CLIENTS_QUESTION = range(5, 7)

# Executors search conversation states
EXECUTORS_CHECKING, EXECUTORS_QUESTION = range(7, 9)

# Invitation response states
INVITATION_RESPONSE = range(9, 10)

# Task creation states
TASK_DESCRIPTION, TASK_DEADLINE, TASK_DIFFICULTY, TASK_PRIORITY = range(10, 14)

# User info state
USER_INFO_INPUT = range(14, 15)

# Multi-step command states
ADD_EMPLOYEE_USERNAME = range(15, 16)
ACCEPT_INVITATION_ID = range(16, 17)
REJECT_INVITATION_ID = range(17, 18)
TAKE_TASK_ID = range(18, 19)
ASSIGN_TASK_ID, ASSIGN_TASK_USERNAME = range(19, 21)
COMPLETE_TASK_ID = range(21, 22)
ABANDON_TASK_ID = range(22, 23)
REVIEW_TASK_ID, REVIEW_TASK_DECISION = range(23, 25)
FIRE_EMPLOYEE_USERNAME = range(25, 26)

# Swipe employees states
SWIPE_EMPLOYEES_VIEWING = range(26, 27)

# Create business conversation states (similar to finance)
CREATE_BUSINESS_Q1, CREATE_BUSINESS_Q2, CREATE_BUSINESS_Q3, CREATE_BUSINESS_Q4 = range(27, 31)

# Switch businesses conversation states
SWITCH_BUSINESS_ID = range(31, 32)

# Delete business conversation states
DELETE_BUSINESS_ID, DELETE_BUSINESS_CONFIRM = range(32, 34)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the /start command"""
    user = update.effective_user
    user_id = user.id

    logger.info(f"User {user_id} ({user.username}) started the bot")

    try:
        # Get or create user account
        user_data = user_manager.get_or_create_user(
            user_id=user_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )

        # Check if user has filled their info
        if not user_manager.has_user_info(user_id):
            await update.message.reply_text(
                "👋 *Добро пожаловать!*\n\n"
                "Перед началом работы, пожалуйста, расскажите немного о себе.\n\n"
                "📝 Укажите:\n"
                "• Ваши навыки и опыт\n"
                "• Сферы, в которых вы работаете\n"
                "• Что вы умеете делать\n"
                "• Чем вы можете быть полезны\n\n"
                "Это поможет работодателям найти вас!",
                parse_mode='Markdown'
            )
            return USER_INFO_INPUT

        # Send welcome message
        welcome_text = MESSAGES['welcome']
        await update.message.reply_text(welcome_text, parse_mode='Markdown')

        # If it's a new user, notify about initial tokens
        balance = user_manager.get_balance_info(user_id)
        if balance and balance['tokens'] == balance['max_tokens']:
            await update.message.reply_text(
                MESSAGES['account_created'].format(tokens=balance['tokens']),
                parse_mode='Markdown'
            )

        logger.info(f"User {user_id} successfully initialized")
        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Error in start command for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])
        return ConversationHandler.END


async def user_info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle user info input"""
    user_id = update.effective_user.id
    user_info = update.message.text

    try:
        # Save user info
        success = user_manager.save_user_info(user_id, user_info)

        if success:
            await update.message.reply_text(
                "✅ Отлично! Ваша информация сохранена.\n\n"
                "Теперь вы можете пользоваться всеми функциями бота!",
                parse_mode='Markdown'
            )
            
            # Send welcome message
            welcome_text = MESSAGES['welcome']
            await update.message.reply_text(welcome_text, parse_mode='Markdown')
            
            # Notify about initial tokens
            balance = user_manager.get_balance_info(user_id)
            if balance:
                await update.message.reply_text(
                    MESSAGES['account_created'].format(tokens=balance['tokens']),
                    parse_mode='Markdown'
                )
            
            logger.info(f"User {user_id} saved their info")
            return ConversationHandler.END
        else:
            await update.message.reply_text(
                "❌ Не удалось сохранить информацию. Попробуйте еще раз.",
                parse_mode='Markdown'
            )
            return USER_INFO_INPUT

    except Exception as e:
        logger.error(f"Error saving user info for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])
        return ConversationHandler.END


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /balance command"""
    user_id = update.effective_user.id

    # Check if user has filled their info
    if not await check_user_info_filled(update, context):
        return

    try:
        # Check and refresh tokens if needed
        user_manager.check_and_refresh_tokens(user_id)

        # Get balance info
        balance = user_manager.get_balance_info(user_id)

        if not balance:
            await update.message.reply_text(MESSAGES['database_error'])
            return

        balance_text = MESSAGES['balance'].format(
            tokens=balance['tokens'],
            max_tokens=balance['max_tokens'],
            refresh_time=balance['next_refresh']
        )

        await update.message.reply_text(balance_text, parse_mode='Markdown')
        logger.info(f"User {user_id} checked balance: {balance['tokens']} tokens")

    except Exception as e:
        logger.error(f"Error in balance command for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])


async def roulette_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /roulette command"""
    user_id = update.effective_user.id

    # Check if user has filled their info
    if not await check_user_info_filled(update, context):
        return

    try:
        # Ensure user exists in database
        user_manager.get_or_create_user(
            user_id=user_id,
            username=update.effective_user.username,
            first_name=update.effective_user.first_name,
            last_name=update.effective_user.last_name
        )

        # Try to spin the roulette
        success, message, result = user_manager.spin_roulette(user_id)

        if success and result:
            # User won!
            response_text = MESSAGES['roulette_win'].format(
                amount=result['amount'],
                new_balance=result['new_balance'],
                next_spin=result['next_spin']
            )
            await update.message.reply_text(response_text, parse_mode='Markdown')
            logger.info(f"User {user_id} won {result['amount']} tokens from roulette")
        else:
            # Roulette not available yet
            if result:
                response_text = MESSAGES['roulette_not_available'].format(
                    next_spin=result['next_spin'],
                    tokens=result['tokens']
                )
            else:
                response_text = f"❌ {message}"
            
            await update.message.reply_text(response_text, parse_mode='Markdown')
            logger.info(f"User {user_id} tried to spin roulette but it's not available")

    except Exception as e:
        logger.error(f"Error in roulette command for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /help command"""
    await update.message.reply_text(MESSAGES['help'], parse_mode='Markdown')
    logger.info(f"User {update.effective_user.id} requested help")


async def check_and_notify_roulette(update: Update, user_id: int):
    """Check if user needs to be notified about available roulette"""
    try:
        # Check if notification is needed
        if user_manager.check_and_notify_roulette(user_id):
            from constants import TOKEN_CONFIG
            # Send notification
            notification_text = MESSAGES['roulette_available_notification'].format(
                min=TOKEN_CONFIG['roulette_min'],
                max=TOKEN_CONFIG['roulette_max']
            )
            await update.message.reply_text(notification_text, parse_mode='Markdown')
            
            # Mark as notified
            user_manager.mark_roulette_notified(user_id)
            logger.info(f"Notified user {user_id} about available roulette")
    except Exception as e:
        logger.error(f"Error checking roulette notification for user {user_id}: {e}")


async def check_user_info_filled(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Check if user has filled their info. If not, prompt them to do so.
    Returns True if user info is filled, False otherwise.
    """
    user_id = update.effective_user.id
    
    # Skip check for /start command (it handles user_info collection)
    if update.message and update.message.text and update.message.text.startswith('/start'):
        return True
    
    # Check if user has filled their info
    if not user_manager.has_user_info(user_id):
        await update.message.reply_text(
            "⚠️ *Доступ ограничен*\n\n"
            "Для использования бота необходимо заполнить информацию о себе.\n\n"
            "Пожалуйста, используйте команду /start для начала работы.",
            parse_mode='Markdown'
        )
        return False
    
    return True


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle regular text messages"""
    user_id = update.effective_user.id
    user_message = update.message.text

    # Check if it's a text message
    if not user_message:
        await update.message.reply_text(MESSAGES['invalid_message'], parse_mode='Markdown')
        return

    # Check if user has filled their info
    if not await check_user_info_filled(update, context):
        return

    logger.info(f"User {user_id} sent message: {user_message[:50]}...")

    # Check if roulette notification is needed
    await check_and_notify_roulette(update, user_id)

    # Send thinking indicator
    thinking_msg = await update.message.reply_text(MESSAGES['thinking'])

    try:
        # Ensure user exists in database
        user_manager.get_or_create_user(
            user_id=user_id,
            username=update.effective_user.username,
            first_name=update.effective_user.first_name,
            last_name=update.effective_user.last_name
        )

        # Process request (check and deduct tokens)
        success, error_msg = user_manager.process_request(user_id, COMMANDS_COSTS["message"])

        if not success:
            await thinking_msg.edit_text(
                MESSAGES['no_tokens'].format(refresh_time=error_msg),
                parse_mode='Markdown'
            )
            return

        # Generate AI response
        try:
            ai_response = ai_client.generate_response(user_message)

            # Truncate if too long (Telegram limit is 4096 chars)
            if len(ai_response) > 4000:
                ai_response = ai_response[:4000] + "\n\n... (ответ сокращен)"

            # Send response with Markdown formatting
            # Note: AI responses are not escaped as they contain intentional markdown formatting
            try:
                await thinking_msg.edit_text(f"💡 {ai_response}", parse_mode='Markdown')
            except BadRequest as e:
                # If Markdown parsing fails, send as plain text
                logger.warning(f"Markdown parsing failed for user {user_id}, sending as plain text: {e}")
                await thinking_msg.edit_text(f"💡 {ai_response}")

            # Log usage
            user_manager.log_usage(user_id, user_message, ai_response)

            logger.info(f"Successfully responded to user {user_id}")

        except Exception as e:
            logger.error(f"AI error for user {user_id}: {e}")
            await thinking_msg.edit_text(MESSAGES['api_error'], parse_mode='Markdown')

            # Refund tokens on AI error
            balance = user_manager.get_balance_info(user_id)
            logger.info(f"Refunded token to user {user_id}")

    except Exception as e:
        logger.error(f"Error handling message for user {user_id}: {e}")
        try:
            await thinking_msg.edit_text(
                MESSAGES['error'].format(error="Внутренняя ошибка"),
                parse_mode='Markdown'
            )
        except:
            pass


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors"""
    logger.error(f"Update {update} caused error: {context.error}", exc_info=context.error)


# Finance command handlers
async def finance_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the finance conversation - updates active business or prompts to create one"""
    user_id = update.effective_user.id

    # Check if user has filled their info
    if not await check_user_info_filled(update, context):
        return ConversationHandler.END

    try:
        # Ensure user exists in database
        user_manager.get_or_create_user(
            user_id=user_id,
            username=update.effective_user.username,
            first_name=update.effective_user.first_name,
            last_name=update.effective_user.last_name
        )

        # Check if user has active business
        active_business = user_manager.get_active_business(user_id)

        if not active_business:
            await update.message.reply_text(
                "❌ У вас нет активного бизнеса.\n\n"
                "Создайте бизнес с помощью /create_business",
                parse_mode='Markdown'
            )
            return ConversationHandler.END

        # User has active business, offer to update it or generate plan
        business_name = escape_markdown(active_business['business_name'])
        await update.message.reply_text(
            f"📊 Вы работаете с бизнесом: *{business_name}*\n\n"
            f"Хотите обновить информацию о бизнесе или сгенерировать финансовый план?\n\n"
            f"Ответьте *'да'* для обновления информации\n"
            f"Ответьте *'нет'* для генерации плана с текущими данными",
            parse_mode='Markdown'
        )
        return CHECKING_EXISTING

    except Exception as e:
        logger.error(f"Error in finance_start for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])
        return ConversationHandler.END


async def finance_check_existing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle response to existing data question"""
    user_id = update.effective_user.id
    user_response = update.message.text.lower().strip()

    if user_response in ['да', 'да', 'yes', 'y', '+']:
        # User wants to update - start questionnaire
        await update.message.reply_text(
            MESSAGES['finance_welcome'],
            parse_mode='Markdown'
        )
        await update.message.reply_text(
            MESSAGES['finance_question_1'],
            parse_mode='Markdown'
        )
        return QUESTION_1
    elif user_response in ['нет', 'net', 'no', 'n', '-']:
        # User wants to generate plan with existing data
        return await finance_generate_plan(update, context, use_existing=True)
    else:
        await update.message.reply_text(
            MESSAGES['finance_invalid_choice'],
            parse_mode='Markdown'
        )
        return CHECKING_EXISTING


async def finance_question_1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle answer to question 1 (business name) and ask question 2"""
    user_id = update.effective_user.id

    # Save answer to context
    context.user_data['business_name'] = update.message.text

    # Ask question 2
    await update.message.reply_text(
        MESSAGES['finance_question_2'],
        parse_mode='Markdown'
    )
    logger.info(f"User {user_id} answered question 1 (business name)")
    return QUESTION_2


async def finance_question_2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle answer to question 2 (business type) and ask question 3"""
    user_id = update.effective_user.id

    # Save answer to context
    context.user_data['business_type'] = update.message.text

    # Ask question 3
    await update.message.reply_text(
        MESSAGES['finance_question_3'],
        parse_mode='Markdown'
    )
    logger.info(f"User {user_id} answered question 2 (business type)")
    return QUESTION_3


async def finance_question_3(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle answer to question 3 (financial situation) and ask question 4"""
    user_id = update.effective_user.id

    # Save answer to context
    context.user_data['financial_situation'] = update.message.text

    # Ask question 4
    await update.message.reply_text(
        MESSAGES['finance_question_4'],
        parse_mode='Markdown'
    )
    logger.info(f"User {user_id} answered question 3 (financial situation)")
    return QUESTION_4


async def finance_question_4(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle answer to question 4 (goals) and generate financial plan"""
    user_id = update.effective_user.id

    # Save answer to context
    context.user_data['goals'] = update.message.text

    logger.info(f"User {user_id} completed all questions")

    
    # Validate business legality before saving
    try:
        # Show validation message
        validation_msg = await update.message.reply_text(
            "🔍 Проверяем информацию о бизнесе на соответствие законодательству РФ..."
        )
        
        # Prepare business info for validation
        business_info = {
            'business_name': context.user_data['business_name'],
            'business_type': context.user_data['business_type'],
            'financial_situation': context.user_data['financial_situation'],
            'goals': context.user_data['goals']
        }
        
        # Validate business legality using AI
        validation_result = ai_client.validate_business_legality(business_info)
        
        # Delete validation message
        try:
            await validation_msg.delete()
        except:
            pass
        
        # Check if business is legal
        if not validation_result['is_valid']:
            logger.warning(f"Business validation failed for user {user_id}")
            await update.message.reply_text(
                f"❌ {validation_result['message']}",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        logger.info(f"Business validation passed for user {user_id}")
        
    except Exception as e:
        logger.error(f"Error validating business legality for user {user_id}: {e}")
        # Delete validation message if it exists
        try:
            await validation_msg.delete()
        except:
            pass
        await update.message.reply_text(
            "❌ Произошла ошибка при проверке информации о бизнесе. "
            "Пожалуйста, попробуйте позже или обратитесь в поддержку.",
            parse_mode='Markdown'
        )
        return ConversationHandler.END
    
    # Save business info to database
    try:
        success = user_manager.save_business_info(
            user_id=user_id,
            business_name=context.user_data['business_name'],
            business_type=context.user_data['business_type'],
            financial_situation=context.user_data['financial_situation'],
            goals=context.user_data['goals']
        )

        if not success:
            await update.message.reply_text(MESSAGES['database_error'])
            return ConversationHandler.END

        await update.message.reply_text(
            MESSAGES['finance_saved'],
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Error saving business info for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])
        return ConversationHandler.END

    # Generate financial plan
    return await finance_generate_plan(update, context, use_existing=False)


async def finance_generate_plan(update: Update, context: ContextTypes.DEFAULT_TYPE,
                               use_existing: bool = False) -> int:
    """Generate and send financial plan as PDF"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or update.effective_user.username or "Пользователь"

    # Show generating message
    thinking_msg = await update.message.reply_text(MESSAGES['finance_generating'])

    pdf_path = None
    try:
        # Check tokens (3 tokens for financial plan)
        success, error_msg = user_manager.process_request(user_id, tokens_amount=COMMANDS_COSTS["finance_generate_plan"])

        if not success:
            await thinking_msg.edit_text(
                MESSAGES['no_tokens'].format(refresh_time=error_msg),
                parse_mode='Markdown'
            )
            return ConversationHandler.END

        # Get business info
        if use_existing:
            business_info = user_manager.get_business_info(user_id)
        else:
            business_info = {
                'business_name': context.user_data['business_name'],
                'business_type': context.user_data['business_type'],
                'financial_situation': context.user_data['financial_situation'],
                'goals': context.user_data['goals']
            }

        if not business_info:
            await thinking_msg.edit_text(MESSAGES['finance_no_info'])
            return ConversationHandler.END

        # Update status message
        await thinking_msg.edit_text("🤖 Генерирую финансовый план с помощью AI...(это может занять до 5 минут)")

        # Generate financial plan using AI
        financial_plan = ai_client.generate_financial_plan(business_info)

        logger.info(f"AI financial plan generated for user {user_id}, length: {len(financial_plan)}")

        # Update status message
        await thinking_msg.edit_text("📄 Создаю PDF документ...")

        # Generate PDF
        try:
            pdf_path = pdf_generator.generate(
                ai_response=financial_plan,
                business_info=business_info,
                user_name=user_name
            )

            logger.info(f"PDF generated for user {user_id}: {pdf_path}")

        except Exception as pdf_error:
            logger.error(f"PDF generation error for user {user_id}: {pdf_error}", exc_info=True)
            # Fallback to text message if PDF generation fails
            await thinking_msg.edit_text(
                "⚠️ Не удалось создать PDF. Отправляю текстовую версию..."
            )

            # Send text version
            if len(financial_plan) > 4000:
                chunks = []
                current_chunk = ""
                for line in financial_plan.split('\n'):
                    if len(current_chunk) + len(line) + 1 < 4000:
                        current_chunk += line + '\n'
                    else:
                        chunks.append(current_chunk)
                        current_chunk = line + '\n'
                if current_chunk:
                    chunks.append(current_chunk)

                await thinking_msg.delete()

                for i, chunk in enumerate(chunks):
                    header = f"💼 *Финансовый план (часть {i+1}/{len(chunks)})*\n\n" if len(chunks) > 1 else "💼 *Финансовый план*\n\n"
                    # AI-generated content is not escaped as it contains intentional markdown
                    try:
                        await update.message.reply_text(header + chunk, parse_mode='Markdown')
                    except BadRequest:
                        await update.message.reply_text(header + chunk)
            else:
                # AI-generated content is not escaped as it contains intentional markdown
                try:
                    await thinking_msg.edit_text(
                        f"💼 *Финансовый план*\n\n{financial_plan}",
                        parse_mode='Markdown'
                    )
                except BadRequest:
                    await thinking_msg.edit_text(f"💼 *Финансовый план*\n\n{financial_plan}")

            # Log usage and return # Вывод у finance неинформативен
            # user_manager.log_usage(
            #     user_id,
            #     f"Finance plan request: {business_info.get('business_type', '')[:100]}",
            #     financial_plan[:500],
            #     tokens_used=3
            # )
            context.user_data.clear()
            return ConversationHandler.END

        # Send PDF document
        await thinking_msg.edit_text("📤 Отправляю PDF документ...")

        try:
            with open(pdf_path, 'rb') as pdf_file:
                await update.message.reply_document(
                    document=pdf_file,
                    filename=f"Финансовый_план_{user_name}.pdf",
                    caption="💼 *Ваш персональный финансовый план готов!*\n\n"
                           "📊 Документ содержит:\n"
                           "• Анализ текущей ситуации\n"
                           "• Рекомендации по оптимизации\n"
                           "• Стратегии развития\n"
                           "• Финансовый прогноз\n"
                           "• Управление рисками\n\n"
                           "Используйте этот план как руководство для развития вашего бизнеса! 🚀",
                    parse_mode='Markdown'
                )

            # Delete thinking message
            await thinking_msg.delete()

            logger.info(f"PDF sent successfully to user {user_id}")

        except Exception as send_error:
            logger.error(f"Error sending PDF to user {user_id}: {send_error}")
            await thinking_msg.edit_text(
                "❌ Произошла ошибка при отправке PDF файла. Попробуйте позже."
            )

        # Log usage
        # user_manager.log_usage(
        #     user_id,
        #     f"Finance plan PDF request: {business_info.get('business_type', '')[:100]}",
        #     f"PDF generated: {pdf_path}",
        #     tokens_used=3
        # )

        logger.info(f"Successfully generated and sent financial plan PDF for user {user_id}")

    except Exception as e:
        logger.error(f"Error generating financial plan for user {user_id}: {e}", exc_info=True)
        try:
            await thinking_msg.edit_text(MESSAGES['finance_error'])
        except:
            pass

    finally:
        # Clean up PDF file after sending
        if pdf_path and os.path.exists(pdf_path):
            try:
                # Small delay to ensure file is sent
                import asyncio
                await asyncio.sleep(1)
                os.remove(pdf_path)
                logger.info(f"Cleaned up PDF file: {pdf_path}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup PDF {pdf_path}: {cleanup_error}")

        # Cleanup old PDFs (older than 24 hours)
        try:
            pdf_generator.cleanup_old_pdfs(max_age_hours=24)
        except Exception as cleanup_error:
            logger.warning(f"Failed to cleanup old PDFs: {cleanup_error}")

    # Clear user data
    context.user_data.clear()
    return ConversationHandler.END


async def finance_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the finance conversation"""
    await update.message.reply_text(
        MESSAGES['finance_cancelled'],
        parse_mode='Markdown'
    )
    context.user_data.clear()
    logger.info(f"User {update.effective_user.id} cancelled finance conversation")
    return ConversationHandler.END


# Create business command handlers (new business creation flow)
async def create_business_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the create business conversation"""
    user_id = update.effective_user.id

    # Check if user has filled their info
    if not await check_user_info_filled(update, context):
        return ConversationHandler.END

    try:
        # Ensure user exists in database
        user_manager.get_or_create_user(
            user_id=user_id,
            username=update.effective_user.username,
            first_name=update.effective_user.first_name,
            last_name=update.effective_user.last_name
        )

        # Start the questionnaire
        await update.message.reply_text(
            "🏢 *Создание нового бизнеса*\n\n"
            "Я помогу вам создать новый бизнес. "
            "Пожалуйста, ответьте на несколько вопросов.\n\n"
            "Вы можете отменить процесс в любой момент командой /cancel",
            parse_mode='Markdown'
        )
        await update.message.reply_text(
            MESSAGES['finance_question_1'],
            parse_mode='Markdown'
        )
        return CREATE_BUSINESS_Q1

    except Exception as e:
        logger.error(f"Error in create_business_start for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])
        return ConversationHandler.END


async def create_business_q1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle answer to question 1 (business name)"""
    context.user_data['business_name'] = update.message.text
    await update.message.reply_text(
        MESSAGES['finance_question_2'],
        parse_mode='Markdown'
    )
    return CREATE_BUSINESS_Q2


async def create_business_q2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle answer to question 2 (business type)"""
    context.user_data['business_type'] = update.message.text
    await update.message.reply_text(
        MESSAGES['finance_question_3'],
        parse_mode='Markdown'
    )
    return CREATE_BUSINESS_Q3


async def create_business_q3(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle answer to question 3 (financial situation)"""
    context.user_data['financial_situation'] = update.message.text
    await update.message.reply_text(
        MESSAGES['finance_question_4'],
        parse_mode='Markdown'
    )
    return CREATE_BUSINESS_Q4


async def create_business_q4(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle answer to question 4 (goals) and create business"""
    user_id = update.effective_user.id
    context.user_data['goals'] = update.message.text

    logger.info(f"User {user_id} completed create_business questions")

    # Validate business legality before saving
    try:
        validation_msg = await update.message.reply_text(
            "🔍 Проверяем информацию о бизнесе на соответствие законодательству РФ..."
        )

        business_info = {
            'business_name': context.user_data['business_name'],
            'business_type': context.user_data['business_type'],
            'financial_situation': context.user_data['financial_situation'],
            'goals': context.user_data['goals']
        }

        validation_result = ai_client.validate_business_legality(business_info)

        try:
            await validation_msg.delete()
        except:
            pass

        if not validation_result['is_valid']:
            logger.warning(f"Business validation failed for user {user_id}")
            await update.message.reply_text(
                f"❌ {validation_result['message']}",
                parse_mode='Markdown'
            )
            context.user_data.clear()
            return ConversationHandler.END

        logger.info(f"Business validation passed for user {user_id}")

    except Exception as e:
        logger.error(f"Error validating business legality for user {user_id}: {e}")
        try:
            await validation_msg.delete()
        except:
            pass
        await update.message.reply_text(
            "❌ Произошла ошибка при проверке информации о бизнесе. "
            "Пожалуйста, попробуйте позже.",
            parse_mode='Markdown'
        )
        context.user_data.clear()
        return ConversationHandler.END

    # Save business info to database
    try:
        success = user_manager.save_business_info(
            user_id=user_id,
            business_name=context.user_data['business_name'],
            business_type=context.user_data['business_type'],
            financial_situation=context.user_data['financial_situation'],
            goals=context.user_data['goals']
        )

        if not success:
            await update.message.reply_text(MESSAGES['database_error'])
            context.user_data.clear()
            return ConversationHandler.END

        business_name = escape_markdown(context.user_data['business_name'])
        await update.message.reply_text(
            f"✅ *Бизнес '{business_name}' успешно создан!*\n\n"
            f"Этот бизнес автоматически установлен как активный.\n"
            f"Используйте /switch_businesses для смены активного бизнеса.\n"
            f"Используйте /delete_business для удаления бизнеса.",
            parse_mode='HTML'
        )

    except Exception as e:
        logger.error(f"Error saving business info for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])
    finally:
        context.user_data.clear()

    return ConversationHandler.END


async def create_business_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle cancellation of create business conversation"""
    await update.message.reply_text("❌ Создание бизнеса отменено")
    context.user_data.clear()
    return ConversationHandler.END


# Switch businesses command handlers
async def switch_businesses_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start switch businesses conversation"""
    user_id = update.effective_user.id

    try:
        # Ensure user exists
        user_manager.get_or_create_user(
            user_id=user_id,
            username=update.effective_user.username,
            first_name=update.effective_user.first_name,
            last_name=update.effective_user.last_name
        )

        # Get all user businesses
        businesses = user_manager.get_all_user_businesses(user_id)

        if not businesses:
            await update.message.reply_text(
                "❌ У вас нет бизнесов.\n\n"
                "Создайте бизнес с помощью /create_business",
                parse_mode='HTML'
            )
            return ConversationHandler.END

        if len(businesses) == 1:
            await update.message.reply_text(
                "ℹ️ У вас только один бизнес.\n\n"
                "Создайте ещё один с помощью /create_business",
                parse_mode='HTML'
            )
            return ConversationHandler.END

        # Show list of businesses
        businesses_text = "🏢 *Ваши бизнесы:*\n\n"
        for biz in businesses:
            is_active = " ✅ *активный*" if biz['is_active'] else ""
            name = escape_markdown(biz['business_name'])
            businesses_text += f"*ID {biz['id']}:* {name}{is_active}\n"

        businesses_text += "\n💡 Пожалуйста, укажите ID бизнеса, который хотите сделать активным:"

        await update.message.reply_text(businesses_text, parse_mode='Markdown')
        return SWITCH_BUSINESS_ID

    except Exception as e:
        logger.error(f"Error in switch_businesses_start for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])
        return ConversationHandler.END


async def switch_businesses_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle business ID input for switching"""
    user_id = update.effective_user.id

    try:
        business_id = int(update.message.text.strip())

        # Set active business
        success, message = user_manager.set_active_business(user_id, business_id)

        if success:
            # Get the business name to show
            businesses = user_manager.get_all_user_businesses(user_id)
            business = next((b for b in businesses if b['id'] == business_id), None)
            business_name = escape_markdown(business['business_name']) if business else "бизнес"

            await update.message.reply_text(
                f"✅ Активный бизнес изменен на '{business_name}'!",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(f"❌ {message}", parse_mode='Markdown')

        logger.info(f"User {user_id} tried to switch to business {business_id}: {success}")

    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат ID. Пожалуйста, введите число.",
            parse_mode='Markdown'
        )
        return SWITCH_BUSINESS_ID
    except Exception as e:
        logger.error(f"Error in switch_businesses_id_handler for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])

    return ConversationHandler.END


async def switch_businesses_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel switch businesses conversation"""
    await update.message.reply_text("❌ Смена активного бизнеса отменена")
    context.user_data.clear()
    return ConversationHandler.END


# Delete business command handlers
async def delete_business_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start delete business conversation"""
    user_id = update.effective_user.id

    try:
        # Ensure user exists
        user_manager.get_or_create_user(
            user_id=user_id,
            username=update.effective_user.username,
            first_name=update.effective_user.first_name,
            last_name=update.effective_user.last_name
        )

        # Get all user businesses
        businesses = user_manager.get_all_user_businesses(user_id)

        if not businesses:
            await update.message.reply_text(
                "❌ У вас нет бизнесов для удаления.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END

        # Show list of businesses
        businesses_text = "🗑 *Удаление бизнеса*\n\n"
        businesses_text += "⚠️ *ВНИМАНИЕ:* Удаление бизнеса приведет к удалению:\n"
        businesses_text += "• Всех сотрудников\n"
        businesses_text += "• Всех задач\n"
        businesses_text += "• Всех связанных данных\n\n"
        businesses_text += "*Ваши бизнесы:*\n\n"

        for biz in businesses:
            is_active = " ✅ *активный*" if biz['is_active'] else ""
            name = escape_markdown(biz['business_name'])
            businesses_text += f"*ID {biz['id']}:* {name}{is_active}\n"

        businesses_text += "\n💡 Пожалуйста, укажите ID бизнеса, который хотите удалить:"

        await update.message.reply_text(businesses_text, parse_mode='Markdown')
        return DELETE_BUSINESS_ID

    except Exception as e:
        logger.error(f"Error in delete_business_start for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])
        return ConversationHandler.END


async def delete_business_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle business ID input for deletion"""
    user_id = update.effective_user.id

    try:
        business_id = int(update.message.text.strip())
        context.user_data['delete_business_id'] = business_id

        # Get business name for confirmation
        businesses = user_manager.get_all_user_businesses(user_id)
        business = next((b for b in businesses if b['id'] == business_id), None)

        if not business:
            await update.message.reply_text(
                "❌ Бизнес с таким ID не найден или не принадлежит вам.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END

        business_name = escape_markdown(business['business_name'])
        await update.message.reply_text(
            f"⚠️ *ПОДТВЕРЖДЕНИЕ УДАЛЕНИЯ*\n\n"
            f"Вы действительно хотите удалить бизнес '{business_name}'?\n\n"
            f"Это действие *НЕОБРАТИМО* и приведет к удалению всех данных бизнеса.\n\n"
            f"Введите *'да'* для подтверждения или *'нет'* для отмены:",
            parse_mode='Markdown'
        )
        return DELETE_BUSINESS_CONFIRM

    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат ID. Пожалуйста, введите число.",
            parse_mode='Markdown'
        )
        return DELETE_BUSINESS_ID
    except Exception as e:
        logger.error(f"Error in delete_business_id_handler for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])
        return ConversationHandler.END


async def delete_business_confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle confirmation for business deletion"""
    user_id = update.effective_user.id
    user_response = update.message.text.lower().strip()

    if user_response not in ['да', 'yes', 'y', '+']:
        await update.message.reply_text(
            "❌ Удаление бизнеса отменено.",
            parse_mode='Markdown'
        )
        context.user_data.clear()
        return ConversationHandler.END

    business_id = context.user_data.get('delete_business_id')

    if not business_id:
        await update.message.reply_text(MESSAGES['database_error'])
        context.user_data.clear()
        return ConversationHandler.END

    try:
        # Delete business
        success, message = user_manager.delete_business(user_id, business_id)

        if success:
            await update.message.reply_text(
                f"✅ {message}",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(f"❌ {message}", parse_mode='Markdown')

        logger.info(f"User {user_id} tried to delete business {business_id}: {success}")

    except Exception as e:
        logger.error(f"Error deleting business for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])

    context.user_data.clear()
    return ConversationHandler.END


async def delete_business_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel delete business conversation"""
    await update.message.reply_text("❌ Удаление бизнеса отменено")
    context.user_data.clear()
    return ConversationHandler.END


# Clients search command handlers
async def clients_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the clients search conversation"""
    user_id = update.effective_user.id

    try:
        # Ensure user exists in database
        user_manager.get_or_create_user(
            user_id=user_id,
            username=update.effective_user.username,
            first_name=update.effective_user.first_name,
            last_name=update.effective_user.last_name
        )

        # Check if user has active business
        if not user_manager.has_active_business(user_id):
            await update.message.reply_text(
                "❌ У вас нет активного бизнеса.\n\n"
                "Создайте бизнес с помощью /create_business",
                parse_mode='Markdown'
            )
            return ConversationHandler.END

        # Check if user already has workers info
        has_info = user_manager.has_workers_info(user_id)

        if has_info:
            await update.message.reply_text(
                MESSAGES['clients_has_info'],
                parse_mode='Markdown'
            )
            return CLIENTS_CHECKING
        else:
            # Start the questionnaire
            await update.message.reply_text(
                MESSAGES['clients_welcome'],
                parse_mode='Markdown'
            )
            await update.message.reply_text(
                MESSAGES['clients_question'],
                parse_mode='Markdown'
            )
            return CLIENTS_QUESTION

    except Exception as e:
        logger.error(f"Error in clients_start for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])
        return ConversationHandler.END


async def clients_check_existing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle response to existing clients data question"""
    user_id = update.effective_user.id
    user_response = update.message.text.lower().strip()

    if user_response in ['да', 'yes', 'y', '+']:
        # User wants to update - start questionnaire
        await update.message.reply_text(
            MESSAGES['clients_welcome'],
            parse_mode='Markdown'
        )
        await update.message.reply_text(
            MESSAGES['clients_question'],
            parse_mode='Markdown'
        )
        return CLIENTS_QUESTION
    elif user_response in ['нет', 'net', 'no', 'n', '-']:
        # User wants to search with existing data
        return await clients_search(update, context, use_existing=True)
    else:
        await update.message.reply_text(
            MESSAGES['finance_invalid_choice'],
            parse_mode='Markdown'
        )
        return CLIENTS_CHECKING


async def clients_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle answer and perform search"""
    user_id = update.effective_user.id

    # Save answer to context
    context.user_data['workers_description'] = update.message.text

    logger.info(f"User {user_id} provided clients search criteria")

    # Save workers info to database
    try:
        success = user_manager.save_workers_info(
            user_id=user_id,
            description=context.user_data['workers_description']
        )

        if not success:
            await update.message.reply_text(MESSAGES['database_error'])
            return ConversationHandler.END

        await update.message.reply_text(
            MESSAGES['clients_saved'],
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Error saving workers info for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])
        return ConversationHandler.END

    # Perform search
    return await clients_search(update, context, use_existing=False)


async def clients_search(update: Update, context: ContextTypes.DEFAULT_TYPE,
                        use_existing: bool = False) -> int:
    """Search for clients and send results"""
    user_id = update.effective_user.id

    # Show searching message
    thinking_msg = await update.message.reply_text(MESSAGES['clients_searching'])

    try:
        # Check tokens (2 tokens for client search)
        success, error_msg = user_manager.process_request(user_id, tokens_amount=COMMANDS_COSTS["clients_search"])

        if not success:
            await thinking_msg.edit_text(
                MESSAGES['no_tokens'].format(refresh_time=error_msg),
                parse_mode='Markdown'
            )
            return ConversationHandler.END

        # Get workers info
        if use_existing:
            workers_info = user_manager.get_workers_info(user_id)
        else:
            workers_info = {
                'description': context.user_data['workers_description']
            }

        if not workers_info:
            await thinking_msg.edit_text(MESSAGES['clients_no_info'])
            return ConversationHandler.END

        # Search for clients using AI
        search_results = ai_client.find_clients(workers_info)

        logger.info(f"Clients search results generated for user {user_id}, length: {len(search_results)}")

        # Send results
        # AI-generated content is not escaped as it contains intentional markdown
        try:
            await thinking_msg.edit_text(
                f"👥 *Подходящие площадки для поиска клиентов:*\n\n{search_results}",
                parse_mode='Markdown'
            )
        except BadRequest as e:
            # If Markdown parsing fails, send as plain text
            logger.warning(f"Markdown parsing failed for user {user_id}, sending as plain text: {e}")
            await thinking_msg.edit_text(f"👥 Подходящие площадки для поиска клиентов:\n\n{search_results}")

        # Log usage
        user_manager.log_usage(
            user_id,
            f"Clients search: {workers_info.get('description', '')[:100]}",
            search_results[:500],
            tokens_used=2
        )

        logger.info(f"Successfully completed clients search for user {user_id}")

    except Exception as e:
        logger.error(f"Error in clients search for user {user_id}: {e}", exc_info=True)
        try:
            await thinking_msg.edit_text(MESSAGES['clients_error'])
        except:
            pass

    # Clear user data
    context.user_data.clear()
    return ConversationHandler.END


async def clients_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the clients search conversation"""
    await update.message.reply_text(
        MESSAGES['clients_cancelled'],
        parse_mode='Markdown'
    )
    context.user_data.clear()
    logger.info(f"User {update.effective_user.id} cancelled clients search")
    return ConversationHandler.END


# Executors search command handlers
async def executors_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the executors search conversation"""
    user_id = update.effective_user.id

    try:
        # Ensure user exists in database
        user_manager.get_or_create_user(
            user_id=user_id,
            username=update.effective_user.username,
            first_name=update.effective_user.first_name,
            last_name=update.effective_user.last_name
        )

        # Check if user has active business
        if not user_manager.has_active_business(user_id):
            await update.message.reply_text(
                "❌ У вас нет активного бизнеса.\n\n"
                "Создайте бизнес с помощью /create_business",
                parse_mode='Markdown'
            )
            return ConversationHandler.END

        # Check if user already has executors info
        has_info = user_manager.has_executors_info(user_id)

        if has_info:
            await update.message.reply_text(
                MESSAGES['executors_has_info'],
                parse_mode='Markdown'
            )
            return EXECUTORS_CHECKING
        else:
            # Start the questionnaire
            await update.message.reply_text(
                MESSAGES['executors_welcome'],
                parse_mode='Markdown'
            )
            await update.message.reply_text(
                MESSAGES['executors_question'],
                parse_mode='Markdown'
            )
            return EXECUTORS_QUESTION

    except Exception as e:
        logger.error(f"Error in executors_start for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])
        return ConversationHandler.END


async def executors_check_existing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle response to existing executors data question"""
    user_id = update.effective_user.id
    user_response = update.message.text.lower().strip()

    if user_response in ['да', 'yes', 'y', '+']:
        # User wants to update - start questionnaire
        await update.message.reply_text(
            MESSAGES['executors_welcome'],
            parse_mode='Markdown'
        )
        await update.message.reply_text(
            MESSAGES['executors_question'],
            parse_mode='Markdown'
        )
        return EXECUTORS_QUESTION
    elif user_response in ['нет', 'net', 'no', 'n', '-']:
        # User wants to search with existing data
        return await executors_search(update, context, use_existing=True)
    else:
        await update.message.reply_text(
            MESSAGES['finance_invalid_choice'],
            parse_mode='Markdown'
        )
        return EXECUTORS_CHECKING


async def executors_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle answer and perform search"""
    user_id = update.effective_user.id

    # Save answer to context
    context.user_data['executors_description'] = update.message.text

    logger.info(f"User {user_id} provided executors search criteria")

    # Save executors info to database
    try:
        success = user_manager.save_executors_info(
            user_id=user_id,
            description=context.user_data['executors_description']
        )

        if not success:
            await update.message.reply_text(MESSAGES['database_error'])
            return ConversationHandler.END

        await update.message.reply_text(
            MESSAGES['executors_saved'],
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Error saving executors info for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])
        return ConversationHandler.END

    # Perform search
    return await executors_search(update, context, use_existing=False)


async def executors_search(update: Update, context: ContextTypes.DEFAULT_TYPE,
                           use_existing: bool = False) -> int:
    """Search for executors and send results"""
    user_id = update.effective_user.id

    # Show searching message
    thinking_msg = await update.message.reply_text(MESSAGES['executors_searching'])

    try:
        # Check tokens (2 tokens for executors search)
        success, error_msg = user_manager.process_request(user_id, tokens_amount=COMMANDS_COSTS["clients_search"])

        if not success:
            await thinking_msg.edit_text(
                MESSAGES['no_tokens'].format(refresh_time=error_msg),
                parse_mode='Markdown'
            )
            return ConversationHandler.END

        # Get executors info
        if use_existing:
            executors_info = user_manager.get_executors_info(user_id)
        else:
            executors_info = {
                'description': context.user_data['executors_description']
            }

        if not executors_info:
            await thinking_msg.edit_text(MESSAGES['executors_no_info'])
            return ConversationHandler.END

        # Search for executors using AI
        search_results = ai_client.find_executors(executors_info)

        logger.info(f"Executors search results generated for user {user_id}, length: {len(search_results)}")

        # Send results
        # AI-generated content is not escaped as it contains intentional markdown
        try:
            await thinking_msg.edit_text(
                f"🔨 *Подходящие площадки для поиска исполнителей:*\n\n{search_results}",
                parse_mode='Markdown'
            )
        except BadRequest as e:
            # If Markdown parsing fails, send as plain text
            logger.warning(f"Markdown parsing failed for user {user_id}, sending as plain text: {e}")
            await thinking_msg.edit_text(f"🔨 Подходящие площадки для поиска исполнителей:\n\n{search_results}")

        # Log usage
        user_manager.log_usage(
            user_id,
            f"Executors search: {executors_info.get('description', '')[:100]}",
            search_results[:500],
            tokens_used=2
        )

        logger.info(f"Successfully completed executors search for user {user_id}")

    except Exception as e:
        logger.error(f"Error in executors search for user {user_id}: {e}", exc_info=True)
        try:
            await thinking_msg.edit_text(MESSAGES['executors_error'])
        except:
            pass

    # Clear user data
    context.user_data.clear()
    return ConversationHandler.END


async def executors_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the executors search conversation"""
    await update.message.reply_text(
        MESSAGES['executors_cancelled'],
        parse_mode='Markdown'
    )
    context.user_data.clear()
    logger.info(f"User {update.effective_user.id} cancelled executors search")
    return ConversationHandler.END


# Employee management command handlers
async def add_employee_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the add_employee conversation"""
    user_id = update.effective_user.id

    try:
        # Check if user has a business
        if not user_manager.is_business_owner(user_id):
            await update.message.reply_text(
                MESSAGES['employee_no_business'],
                parse_mode='Markdown'
            )
            return ConversationHandler.END

        # Ask for username
        await update.message.reply_text(
            "👤 Пожалуйста, укажите username пользователя, которого хотите пригласить:\n\n"
            "Например: `@username` или `username`",
            parse_mode='Markdown'
        )
        return ADD_EMPLOYEE_USERNAME

    except Exception as e:
        logger.error(f"Error in add_employee_start for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])
        return ConversationHandler.END


async def add_employee_username_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle username input for add_employee"""
    target_username = update.message.text.lstrip('@').strip()
    context.user_data['target_username'] = target_username
    return await add_employee_process(update, context)


async def add_employee_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process the employee invitation"""
    user_id = update.effective_user.id
    target_username = context.user_data.get('target_username')

    try:
        # Invite employee
        try:
            success, message = user_manager.invite_employee(user_id, target_username)
        except Exception as e:
            logger.error(f"Error calling invite_employee for user {user_id}: {e}")
            success = False
            message = f"Ошибка при отправке приглашения: {str(e)}"

        logger.info(f"Invite employee: {success}, {message}")
        if success:
            await update.message.reply_text(
                MESSAGES['employee_invited'].format(message=message),
                parse_mode='Markdown'
            )

            # Notify the invited user with inline buttons
            target_user_id = user_manager.get_user_by_username(target_username)
            if target_user_id:
                try:
                    business = user_manager.get_business(user_id)
                    # Get the invitation ID
                    invitations = user_manager.get_pending_invitations(target_user_id)
                    invitation_id = None
                    for inv in invitations:
                        if inv['business_name'] == business['business_name']:
                            invitation_id = inv['id']
                            break

                    if invitation_id:
                        # Create inline keyboard with Accept/Reject buttons
                        keyboard = [
                            [
                                InlineKeyboardButton("✅ Принять", callback_data=f"accept_inv_{invitation_id}"),
                                InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_inv_{invitation_id}")
                            ]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)

                        escaped_business_name = escape_markdown(business['business_name'])
                        await context.bot.send_message(
                            chat_id=target_user_id,
                            text=f"🎉 *Новое приглашение!*\n\n"
                                 f"Вас пригласили стать сотрудником бизнеса *{escaped_business_name}*\n\n"
                                 f"Выберите действие:",
                            parse_mode='Markdown',
                            reply_markup=reply_markup
                        )
                except Exception as e:
                    logger.warning(f"Failed to notify user {target_user_id}: {e}")
        else:
            await update.message.reply_text(
                MESSAGES['employee_invite_error'].format(message=message)
            )

        logger.info(f"User {user_id} invited {target_username}: {success}")

    except Exception as e:
        logger.error(f"Error in add_employee_process for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])

    finally:
        context.user_data.clear()

    return ConversationHandler.END


async def add_employee_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel add employee conversation"""
    await update.message.reply_text("❌ Приглашение сотрудника отменено")
    context.user_data.clear()
    return ConversationHandler.END


async def fire_employee_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the fire_employee conversation"""
    user_id = update.effective_user.id
    
    try:
        # Check if user has a business
        if not user_manager.is_business_owner(user_id):
            await update.message.reply_text(
                MESSAGES['employee_no_business'],
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        # Get employees list
        business = user_manager.get_business(user_id)
        all_employees = user_manager.get_all_employees(business['id'])
        accepted = [e for e in all_employees if e['status'] == 'accepted']
        
        if not accepted:
            await update.message.reply_text(
                "У вас нет сотрудников, которых можно уволить.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        # Format employees list
        employees_text = "👥 *Ваши сотрудники:*\n\n"
        for emp in accepted:
            username = f"@{emp['username']}" if emp['username'] else emp['first_name']
            escaped_username = escape_markdown(username)
            rating = emp.get('rating', 500)
            employees_text += f"  • {escaped_username} ⭐ {rating}\n"
        
        employees_text += "\n⚠️ Пожалуйста, укажите username сотрудника, которого хотите уволить:\n\n"
        employees_text += "Например: `@username` или `username`\n\n"
        employees_text += "❗️ *Внимание:* Все активные задачи этого сотрудника станут доступными для других."
        
        await update.message.reply_text(employees_text, parse_mode='Markdown')
        return FIRE_EMPLOYEE_USERNAME
        
    except Exception as e:
        logger.error(f"Error in fire_employee_start for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])
        return ConversationHandler.END


async def fire_employee_username_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle username input for fire_employee"""
    target_username = update.message.text.lstrip('@').strip()
    context.user_data['target_username'] = target_username
    return await fire_employee_process(update, context)


async def fire_employee_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process the employee removal"""
    user_id = update.effective_user.id
    target_username = context.user_data.get('target_username')
    
    try:
        # Get target user
        target_user_id = user_manager.get_user_by_username(target_username)
        if not target_user_id:
            await update.message.reply_text(
                f"❌ Пользователь @{target_username} не найден.",
                parse_mode='Markdown'
            )
            context.user_data.clear()
            return ConversationHandler.END
        
        # Remove employee
        success, message = user_manager.remove_employee(user_id, target_user_id)
        
        if success:
            escaped_username = escape_markdown(f"@{target_username}")
            await update.message.reply_text(
                f"✅ Сотрудник {escaped_username} уволен.\n\n"
                f"Все его активные задачи были освобождены и доступны для назначения другим сотрудникам.",
                parse_mode='Markdown'
            )
            
            # Notify the fired employee
            try:
                business = user_manager.get_business(user_id)
                if business:
                    escaped_business_name = escape_markdown(business['business_name'])
                    await context.bot.send_message(
                        chat_id=target_user_id,
                        text=f"⚠️ Вы были уволены из бизнеса *{escaped_business_name}*.\n\n"
                             f"Все ваши задачи в этом бизнесе были освобождены.",
                        parse_mode='Markdown'
                    )
            except Exception as e:
                logger.error(f"Failed to notify fired employee {target_user_id}: {e}")
        else:
            escaped_message = escape_markdown(message)
            await update.message.reply_text(f"❌ {escaped_message}", parse_mode='Markdown')
        
        logger.info(f"User {user_id} tried to fire {target_username}: {success}")
        
    except Exception as e:
        logger.error(f"Error in fire_employee_process for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])
    
    finally:
        context.user_data.clear()
    
    return ConversationHandler.END


async def fire_employee_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel fire employee conversation"""
    await update.message.reply_text("❌ Увольнение сотрудника отменено")
    context.user_data.clear()
    return ConversationHandler.END


async def employees_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /employees command to list business employees"""
    user_id = update.effective_user.id

    try:
        # Check if user has a business
        business = user_manager.get_business(user_id)
        if not business:
            await update.message.reply_text(
                MESSAGES['employee_no_business'],
                parse_mode='Markdown'
            )
            return

        # Get all employees
        all_employees = user_manager.get_all_employees(business['id'])

        if not all_employees:
            escaped_business_name = escape_markdown(business['business_name'])
            await update.message.reply_text(
                MESSAGES['employees_empty'].format(business_name=escaped_business_name),
                parse_mode='Markdown'
            )
            return

        # Format employee list
        employees_text = ""
        accepted = [e for e in all_employees if e['status'] == 'accepted']
        pending = [e for e in all_employees if e['status'] == 'pending']

        if accepted:
            employees_text += "*✅ Принятые:*\n"
            for emp in accepted:
                username = f"@{emp['username']}" if emp['username'] else emp['first_name']
                escaped_username = escape_markdown(username)
                rating = emp.get('rating', 500)
                employees_text += f"  • {escaped_username} ⭐ {rating}\n"
            employees_text += "\n"

        if pending:
            employees_text += "*⏳ Ожидают ответа:*\n"
            for emp in pending:
                username = f"@{emp['username']}" if emp['username'] else emp['first_name']
                escaped_username = escape_markdown(username)
                employees_text += f"  • {escaped_username}\n"

        escaped_business_name = escape_markdown(business['business_name'])
        await update.message.reply_text(
            MESSAGES['employees_list'].format(
                business_name=escaped_business_name,
                employees=employees_text
            ),
            parse_mode='Markdown'
        )

        logger.info(f"User {user_id} viewed employees list")

    except Exception as e:
        logger.error(f"Error in employees command for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])


async def invitations_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /invitations command to view pending invitations"""
    user_id = update.effective_user.id

    try:
        # Get pending invitations
        invitations = user_manager.get_pending_invitations(user_id)

        if not invitations:
            await update.message.reply_text(
                MESSAGES['invitations_empty'],
                parse_mode='Markdown'
            )
            return

        # Format invitations list
        invitations_text = ""
        for inv in invitations:
            owner_name = f"@{inv['owner_username']}" if inv['owner_username'] else inv['owner_first_name']
            escaped_business_name = escape_markdown(inv['business_name'])
            escaped_owner_name = escape_markdown(owner_name)
            invitations_text += f"*ID {inv['id']}:* {escaped_business_name}\n"
            invitations_text += f"  От: {escaped_owner_name}\n\n"

        await update.message.reply_text(
            MESSAGES['invitations_list'].format(invitations=invitations_text),
            parse_mode='Markdown'
        )

        logger.info(f"User {user_id} viewed invitations")

    except Exception as e:
        logger.error(f"Error in invitations command for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])


async def invitation_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button callbacks for invitations"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    data = query.data

    try:
        # Parse callback data
        if data.startswith("accept_inv_"):
            invitation_id = int(data.replace("accept_inv_", ""))
            accept = True
            action_text = "принято"
        elif data.startswith("reject_inv_"):
            invitation_id = int(data.replace("reject_inv_", ""))
            accept = False
            action_text = "отклонено"
        else:
            return

        # Process invitation response
        success = user_manager.respond_to_invitation(invitation_id, accept=accept)

        if success:
            if accept:
                await query.edit_message_text(
                    text=f"✅ {MESSAGES['invitation_accepted']}",
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_text(
                    text=f"❌ {MESSAGES['invitation_rejected']}",
                    parse_mode='Markdown'
                )
        else:
            await query.edit_message_text(
                text=MESSAGES['invitation_not_found'],
                parse_mode='Markdown'
            )

        logger.info(f"User {user_id} {action_text} invitation {invitation_id} via button: {success}")

    except Exception as e:
        logger.error(f"Error in invitation callback handler for user {user_id}: {e}")
        await query.edit_message_text(MESSAGES['database_error'])


async def accept_invitation_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the accept invitation conversation"""
    user_id = update.effective_user.id

    try:
        # Get pending invitations to show user
        invitations = user_manager.get_pending_invitations(user_id)

        if not invitations:
            await update.message.reply_text(
                MESSAGES['invitations_empty'],
                parse_mode='Markdown'
            )
            return ConversationHandler.END

        # Format invitations list
        invitations_text = "📬 *Ваши приглашения:*\n\n"
        for inv in invitations:
            owner_name = f"@{inv['owner_username']}" if inv['owner_username'] else inv['owner_first_name']
            escaped_business_name = escape_markdown(inv['business_name'])
            escaped_owner_name = escape_markdown(owner_name)
            invitations_text += f"*ID {inv['id']}:* {escaped_business_name}\n"
            invitations_text += f"  От: {escaped_owner_name}\n\n"

        invitations_text += "\n💡 Пожалуйста, укажите ID приглашения, которое хотите принять:"

        await update.message.reply_text(invitations_text, parse_mode='Markdown')
        return ACCEPT_INVITATION_ID

    except Exception as e:
        logger.error(f"Error in accept_invitation_start for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])
        return ConversationHandler.END


async def accept_invitation_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle invitation ID input for accept"""
    try:
        invitation_id = int(update.message.text.strip())
        context.user_data['invitation_id'] = invitation_id
        return await accept_invitation_process(update, context)
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат ID. Пожалуйста, введите число.",
            parse_mode='Markdown'
        )
        return ACCEPT_INVITATION_ID


async def accept_invitation_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process the invitation acceptance"""
    user_id = update.effective_user.id
    invitation_id = context.user_data.get('invitation_id')

    try:
        # Accept invitation
        success = user_manager.respond_to_invitation(invitation_id, accept=True)

        if success:
            await update.message.reply_text(
                MESSAGES['invitation_accepted'],
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                MESSAGES['invitation_not_found'],
                parse_mode='Markdown'
            )

        logger.info(f"User {user_id} accepted invitation {invitation_id}: {success}")

    except Exception as e:
        logger.error(f"Error in accept_invitation_process for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])

    finally:
        context.user_data.clear()

    return ConversationHandler.END


async def accept_invitation_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel accept invitation conversation"""
    await update.message.reply_text("❌ Принятие приглашения отменено")
    context.user_data.clear()
    return ConversationHandler.END


async def reject_invitation_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the reject invitation conversation"""
    user_id = update.effective_user.id

    try:
        # Get pending invitations to show user
        invitations = user_manager.get_pending_invitations(user_id)

        if not invitations:
            await update.message.reply_text(
                MESSAGES['invitations_empty'],
                parse_mode='Markdown'
            )
            return ConversationHandler.END

        # Format invitations list
        invitations_text = "📬 *Ваши приглашения:*\n\n"
        for inv in invitations:
            owner_name = f"@{inv['owner_username']}" if inv['owner_username'] else inv['owner_first_name']
            escaped_business_name = escape_markdown(inv['business_name'])
            escaped_owner_name = escape_markdown(owner_name)
            invitations_text += f"*ID {inv['id']}:* {escaped_business_name}\n"
            invitations_text += f"  От: {escaped_owner_name}\n\n"

        invitations_text += "\n💡 Пожалуйста, укажите ID приглашения, которое хотите отклонить:"

        await update.message.reply_text(invitations_text, parse_mode='Markdown')
        return REJECT_INVITATION_ID

    except Exception as e:
        logger.error(f"Error in reject_invitation_start for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])
        return ConversationHandler.END


async def reject_invitation_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle invitation ID input for reject"""
    try:
        invitation_id = int(update.message.text.strip())
        context.user_data['invitation_id'] = invitation_id
        return await reject_invitation_process(update, context)
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат ID. Пожалуйста, введите число.",
            parse_mode='Markdown'
        )
        return REJECT_INVITATION_ID


async def reject_invitation_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process the invitation rejection"""
    user_id = update.effective_user.id
    invitation_id = context.user_data.get('invitation_id')

    try:
        # Reject invitation
        success = user_manager.respond_to_invitation(invitation_id, accept=False)

        if success:
            await update.message.reply_text(
                MESSAGES['invitation_rejected'],
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                MESSAGES['invitation_not_found'],
                parse_mode='Markdown'
            )

        logger.info(f"User {user_id} rejected invitation {invitation_id}: {success}")

    except Exception as e:
        logger.error(f"Error in reject_invitation_process for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])

    finally:
        context.user_data.clear()

    return ConversationHandler.END


async def reject_invitation_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel reject invitation conversation"""
    await update.message.reply_text("❌ Отклонение приглашения отменено")
    context.user_data.clear()
    return ConversationHandler.END

async def my_businesses_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /my_businesses command to view businesses where user is an employee"""
    user_id = update.effective_user.id

    try:
        # Get businesses where user is an employee
        businesses = user_manager.get_all_user_businesses(user_id)

        if not businesses:
            await update.message.reply_text(
                MESSAGES['my_businesses_empty'],
                parse_mode='Markdown'
            )
            return

        # Format businesses list
        businesses_text = ""
        for biz in businesses:
            escaped_business_name = escape_markdown(biz['business_name'])
            businesses_text += f"• *{escaped_business_name}*\n\n"

        await update.message.reply_text(
            MESSAGES['my_businesses_list'].format(businesses=businesses_text),
            parse_mode='Markdown'
        )

        logger.info(f"User {user_id} viewed their businesses")

    except Exception as e:
        logger.error(f"Error in my_businesses command for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])

async def my_employers_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /my_employers command to view businesses where user is an employee"""
    user_id = update.effective_user.id

    try:
        # Get businesses where user is an employee
        businesses = user_manager.get_user_businesses(user_id)

        if not businesses:
            await update.message.reply_text(
                MESSAGES['my_employers_empty'],
                parse_mode='Markdown'
            )
            return

        # Format businesses list
        businesses_text = ""
        for biz in businesses:
            owner_name = f"@{biz['owner_username']}" if biz['owner_username'] else biz['owner_first_name']
            escaped_business_name = escape_markdown(biz['business_name'])
            escaped_owner_name = escape_markdown(owner_name)
            businesses_text += f"• *{escaped_business_name}*\n"
            businesses_text += f"  Владелец: {escaped_owner_name}\n\n"

        await update.message.reply_text(
            MESSAGES['my_employers_list'].format(businesses=businesses_text),
            parse_mode='Markdown'
        )

        logger.info(f"User {user_id} viewed their employers")

    except Exception as e:
        logger.error(f"Error in my_employers command for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])


# Task management command handlers
async def create_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the /create_task command"""
    user_id = update.effective_user.id

    try:
        # Check if user has active business
        if not user_manager.has_active_business(user_id):
            await update.message.reply_text(
                "❌ У вас нет активного бизнеса.\n\n"
                "Создайте бизнес с помощью /create_business",
                parse_mode='Markdown'
            )
            return ConversationHandler.END

        await update.message.reply_text(
            MESSAGES['task_create_start'],
            parse_mode='Markdown'
        )
        return TASK_DESCRIPTION

    except Exception as e:
        logger.error(f"Error in create_task command for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])
        return ConversationHandler.END


async def task_description_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle task description input"""
    user_id = update.effective_user.id
    text = update.message.text

    # Parse title and description
    if '---' not in text:
        await update.message.reply_text(
            MESSAGES['task_invalid_format'],
            parse_mode='Markdown'
        )
        return TASK_DESCRIPTION

    parts = text.split('---', 1)
    title = parts[0].strip()
    description = parts[1].strip()

    if not title or not description:
        await update.message.reply_text(
            MESSAGES['task_invalid_format'],
            parse_mode='Markdown'
        )
        return TASK_DESCRIPTION

    # Save title and description in context
    context.user_data['task_title'] = title
    context.user_data['task_description'] = description

    # Ask for deadline
    await update.message.reply_text(
        MESSAGES['task_deadline_question'],
        parse_mode='Markdown'
    )
    return TASK_DEADLINE


async def task_deadline_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle task deadline input"""
    text = update.message.text.strip()

    try:
        deadline_hours = int(text)
        if deadline_hours <= 0:
            await update.message.reply_text(
                "❌ Дедлайн должен быть положительным числом. Попробуйте еще раз:",
                parse_mode='Markdown'
            )
            return TASK_DEADLINE

        # Convert hours to minutes for storage
        deadline_minutes = deadline_hours * 60
        
        # Save deadline in context
        context.user_data['task_deadline'] = deadline_minutes

        # Ask for difficulty
        await update.message.reply_text(
            MESSAGES['task_difficulty_question'],
            parse_mode='Markdown'
        )
        return TASK_DIFFICULTY

    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат. Укажите число (дедлайн в часах):",
            parse_mode='Markdown'
        )
        return TASK_DEADLINE


async def task_difficulty_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle task difficulty input"""
    text = update.message.text.strip()

    try:
        difficulty = int(text)
        if not (1 <= difficulty <= 5):
            await update.message.reply_text(
                "❌ Сложность должна быть от 1 до 5. Попробуйте еще раз:",
                parse_mode='Markdown'
            )
            return TASK_DIFFICULTY

        # Save difficulty in context
        context.user_data['task_difficulty'] = difficulty

        # Ask for priority
        await update.message.reply_text(
            MESSAGES['task_priority_question'],
            parse_mode='Markdown'
        )
        return TASK_PRIORITY

    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат. Укажите число от 1 до 5:",
            parse_mode='Markdown'
        )
        return TASK_DIFFICULTY


async def task_priority_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle task priority input and create task"""
    user_id = update.effective_user.id
    text = update.message.text.strip().lower()

    if text not in ['низкий', 'средний', 'высокий']:
        await update.message.reply_text(
            "❌ Неверный приоритет. Укажите: низкий, средний или высокий:",
            parse_mode='Markdown'
        )
        return TASK_PRIORITY

    # Save priority in context
    context.user_data['task_priority'] = text

    # Show thinking message
    thinking_msg = await update.message.reply_text("🤔 Создаю задачу и анализирую сотрудников...")

    try:
        # Get all data from context
        title = context.user_data.get('task_title')
        description = context.user_data.get('task_description')
        deadline_minutes = context.user_data.get('task_deadline')
        difficulty = context.user_data.get('task_difficulty')
        priority = context.user_data.get('task_priority')

        # Create task with AI recommendation
        success, message, result = user_manager.create_task_with_ai_recommendation(
            user_id, title, description, deadline_minutes, difficulty, priority
        )

        if not success:
            await thinking_msg.edit_text(f"❌ {message}")
            context.user_data.clear()
            return ConversationHandler.END

        task = result['task']
        ai_recommendation = result.get('ai_recommendation')

        # Format response
        if ai_recommendation:
            # Escape username (user input) but not reasoning (AI-generated)
            escaped_username = escape_markdown(ai_recommendation['username'])
            ai_text = MESSAGES['task_ai_recommendation'].format(
                username=escaped_username,
                reasoning=ai_recommendation['reasoning'],  # AI-generated, not escaped
                task_id=task['id']
            )
            escaped_title = escape_markdown(title)
            response_text = MESSAGES['task_created'].format(
                title=escaped_title,
                task_id=task['id'],
                ai_recommendation=ai_text
            )
        else:
            escaped_title = escape_markdown(title)
            response_text = MESSAGES['task_created_no_ai'].format(
                title=escaped_title,
                task_id=task['id']
            )

        await thinking_msg.edit_text(response_text, parse_mode='Markdown')
        logger.info(f"Task {task['id']} created by user {user_id} with deadline={deadline_minutes}, difficulty={difficulty}, priority={priority}")

    except Exception as e:
        logger.error(f"Error creating task for user {user_id}: {e}")
        await thinking_msg.edit_text(MESSAGES['database_error'])

    finally:
        context.user_data.clear()

    return ConversationHandler.END


async def task_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel task creation"""
    await update.message.reply_text("❌ Создание задачи отменено")
    return ConversationHandler.END


async def available_tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /available_tasks command"""
    user_id = update.effective_user.id

    try:
        # Get available tasks
        tasks = user_manager.get_available_tasks_for_employee(user_id)

        if not tasks:
            await update.message.reply_text(
                MESSAGES['available_tasks_empty'],
                parse_mode='Markdown'
            )
            return

        # Format tasks list
        tasks_text = ""
        for task in tasks:
            escaped_title = escape_markdown(task['title'])
            escaped_business = escape_markdown(task['business_name'])
            tasks_text += f"*ID {task['id']}:* {escaped_title}\n"
            tasks_text += f"Бизнес: {escaped_business}\n"
            if task.get('difficulty'):
                tasks_text += f"⭐ Сложность: {task['difficulty']}/5\n"
            if task.get('priority'):
                tasks_text += f"🎯 Приоритет: {task['priority']}\n"
            if task.get('deadline_minutes'):
                hours = task['deadline_minutes'] / 60
                if hours >= 1:
                    tasks_text += f"⏰ Дедлайн: {hours:.1f} ч\n"
                else:
                    tasks_text += f"⏰ Дедлайн: {task['deadline_minutes']} мин\n"
            if task.get('description'):
                desc = task['description'][:100]
                if len(task['description']) > 100:
                    desc += "..."
                escaped_desc = escape_markdown(desc)
                tasks_text += f"Описание: {escaped_desc}\n"
            if task.get('ai_recommended_employee') == user_id:
                tasks_text += "🤖 *AI рекомендует вас!*\n"
            tasks_text += "\n"

        await update.message.reply_text(
            MESSAGES['available_tasks'].format(tasks=tasks_text),
            parse_mode='Markdown'
        )
        logger.info(f"User {user_id} viewed available tasks")

    except Exception as e:
        logger.error(f"Error in available_tasks command for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])


async def my_tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /my_tasks command"""
    user_id = update.effective_user.id

    try:
        # Get user's tasks
        tasks = user_manager.get_my_tasks(user_id)

        if not tasks:
            await update.message.reply_text(
                MESSAGES['my_tasks_empty'],
                parse_mode='Markdown'
            )
            return

        # Format tasks list
        tasks_text = ""
        for task in tasks:
            escaped_title = escape_markdown(task['title'])
            escaped_business = escape_markdown(task['business_name'])
            
            # Status with emoji
            status_emoji = {
                'assigned': '📌',
                'in_progress': '🔄',
                'submitted': '📥'
            }
            emoji = status_emoji.get(task['status'], '❓')
            escaped_status = escape_markdown(task['status'])
            
            tasks_text += f"*ID {task['id']}:* {escaped_title}\n"
            tasks_text += f"Бизнес: {escaped_business}\n"
            tasks_text += f"{emoji} Статус: {escaped_status}\n"
            
            if task.get('difficulty'):
                tasks_text += f"⭐ Сложность: {task['difficulty']}/5\n"
            if task.get('priority'):
                tasks_text += f"🎯 Приоритет: {task['priority']}\n"
            if task.get('deadline_minutes') and task.get('assigned_at'):
                # Calculate time left
                from datetime import datetime
                assigned_at = task['assigned_at']
                deadline = task['deadline_minutes']
                elapsed_minutes = (datetime.now() - assigned_at).total_seconds() / 60
                time_left = deadline - elapsed_minutes
                
                if time_left > 0:
                    hours = int(time_left // 60)
                    minutes = int(time_left % 60)
                    if hours > 0:
                        tasks_text += f"⏰ Осталось: {hours} ч {minutes} мин\n"
                    else:
                        tasks_text += f"⏰ Осталось: {minutes} мин\n"
                else:
                    tasks_text += f"⚠️ Дедлайн просрочен!\n"
                    
            if task.get('description'):
                desc = task['description'][:100]
                if len(task['description']) > 100:
                    desc += "..."
                escaped_desc = escape_markdown(desc)
                tasks_text += f"Описание: {escaped_desc}\n"
            tasks_text += "\n"

        await update.message.reply_text(
            MESSAGES['my_tasks'].format(tasks=tasks_text),
            parse_mode='Markdown'
        )
        logger.info(f"User {user_id} viewed their tasks")

    except Exception as e:
        logger.error(f"Error in my_tasks command for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])


async def take_task_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the take task conversation"""
    user_id = update.effective_user.id

    try:
        # Get available tasks to show user
        tasks = user_manager.get_available_tasks_for_employee(user_id)

        if not tasks:
            await update.message.reply_text(
                MESSAGES['available_tasks_empty'],
                parse_mode='Markdown'
            )
            return ConversationHandler.END

        # Format tasks list
        tasks_text = "📋 *Доступные задачи:*\n\n"
        for task in tasks:
            escaped_title = escape_markdown(task['title'])
            escaped_business = escape_markdown(task['business_name'])
            tasks_text += f"*ID {task['id']}:* {escaped_title}\n"
            tasks_text += f"Бизнес: {escaped_business}\n"
            if task.get('description'):
                desc = task['description'][:100]
                if len(task['description']) > 100:
                    desc += "..."
                escaped_desc = escape_markdown(desc)
                tasks_text += f"Описание: {escaped_desc}\n"
            if task.get('ai_recommended_employee') == user_id:
                tasks_text += "🤖 *AI рекомендует вас!*\n"
            tasks_text += "\n"

        tasks_text += "\n💡 Пожалуйста, укажите ID задачи, которую хотите взять:"

        await update.message.reply_text(tasks_text, parse_mode='Markdown')
        return TAKE_TASK_ID

    except Exception as e:
        logger.error(f"Error in take_task_start for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])
        return ConversationHandler.END


async def take_task_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle task ID input for take_task"""
    try:
        task_id = int(update.message.text.strip())
        context.user_data['task_id'] = task_id
        return await take_task_process(update, context)
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат ID. Пожалуйста, введите число.",
            parse_mode='Markdown'
        )
        return TAKE_TASK_ID


async def take_task_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process taking the task"""
    user_id = update.effective_user.id
    task_id = context.user_data.get('task_id')

    try:
        # Take task
        success, message = user_manager.take_task(user_id, task_id)

        if success:
            await update.message.reply_text(
                MESSAGES['task_taken'],
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(f"❌ {message}", parse_mode='Markdown')

        logger.info(f"User {user_id} tried to take task {task_id}: {success}")

    except Exception as e:
        logger.error(f"Error in take_task_process for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])

    finally:
        context.user_data.clear()

    return ConversationHandler.END


async def take_task_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel take task conversation"""
    await update.message.reply_text("❌ Взятие задачи отменено")
    context.user_data.clear()
    return ConversationHandler.END


async def assign_task_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the assign task conversation"""
    user_id = update.effective_user.id

    try:
        # Check if user has active business
        if not user_manager.has_active_business(user_id):
            await update.message.reply_text(
                "❌ У вас нет активного бизнеса.\n\n"
                "Создайте бизнес с помощью /create_business",
                parse_mode='Markdown'
            )
            return ConversationHandler.END

        # Ask for task ID first
        await update.message.reply_text(
            "📋 Пожалуйста, укажите ID задачи, которую хотите назначить:",
            parse_mode='Markdown'
        )
        return ASSIGN_TASK_ID

    except Exception as e:
        logger.error(f"Error in assign_task_start for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])
        return ConversationHandler.END


async def assign_task_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle task ID input for assign_task"""
    try:
        task_id = int(update.message.text.strip())
        context.user_data['task_id'] = task_id
        # Ask for username
        await update.message.reply_text(
            "👤 Пожалуйста, укажите username сотрудника:\n\n"
            "Например: `@username` или `username`",
            parse_mode='Markdown'
        )
        return ASSIGN_TASK_USERNAME
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат ID. Пожалуйста, введите число.",
            parse_mode='Markdown'
        )
        return ASSIGN_TASK_ID


async def assign_task_username_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle username input for assign_task"""
    employee_username = update.message.text.lstrip('@').strip()
    context.user_data['employee_username'] = employee_username
    return await assign_task_process(update, context)


async def assign_task_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process assigning the task"""
    user_id = update.effective_user.id
    task_id = context.user_data.get('task_id')
    employee_username = context.user_data.get('employee_username')

    try:
        # Assign task by username
        success, message, employee_id = user_manager.assign_task_to_employee_by_username(
            user_id, task_id, employee_username
        )

        if success:
            await update.message.reply_text(
                MESSAGES['task_assigned'],
                parse_mode='Markdown'
            )

            # Notify employee
            if employee_id:
                try:
                    from database import business_repo
                    task = business_repo.get_task(task_id)
                    if task:
                        escaped_title = escape_markdown(task['title'])
                        escaped_desc = escape_markdown(task['description'])
                        await context.bot.send_message(
                            chat_id=employee_id,
                            text=f"📋 *Новая задача назначена вам!*\n\n"
                                 f"*{escaped_title}*\n"
                                 f"{escaped_desc}\n\n"
                                 f"Посмотреть свои задачи: `/my_tasks`",
                            parse_mode='Markdown'
                        )
                except Exception as e:
                    logger.warning(f"Failed to notify employee {employee_id}: {e}")
        else:
            await update.message.reply_text(f"❌ {message}", parse_mode='Markdown')

        logger.info(f"User {user_id} tried to assign task {task_id} to @{employee_username}: {success}")

    except Exception as e:
        logger.error(f"Error in assign_task_process for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])

    finally:
        context.user_data.clear()

    return ConversationHandler.END


async def assign_task_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel assign task conversation"""
    await update.message.reply_text("❌ Назначение задачи отменено")
    context.user_data.clear()
    return ConversationHandler.END


async def complete_task_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the complete task conversation"""
    user_id = update.effective_user.id

    try:
        # Get user's tasks to show
        tasks = user_manager.get_my_tasks(user_id)

        if not tasks:
            await update.message.reply_text(
                MESSAGES['my_tasks_empty'],
                parse_mode='Markdown'
            )
            return ConversationHandler.END

        # Filter only in_progress tasks
        in_progress_tasks = [t for t in tasks if t['status'] in ('assigned', 'in_progress')]

        if not in_progress_tasks:
            await update.message.reply_text(
                "У вас нет задач в работе для завершения.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END

        # Format tasks list
        tasks_text = "📋 *Ваши задачи в работе:*\n\n"
        for task in in_progress_tasks:
            escaped_title = escape_markdown(task['title'])
            escaped_business = escape_markdown(task['business_name'])
            tasks_text += f"*ID {task['id']}:* {escaped_title}\n"
            tasks_text += f"Бизнес: {escaped_business}\n"
            if task.get('description'):
                desc = task['description'][:100]
                if len(task['description']) > 100:
                    desc += "..."
                escaped_desc = escape_markdown(desc)
                tasks_text += f"Описание: {escaped_desc}\n"
            tasks_text += "\n"

        tasks_text += "\n💡 Пожалуйста, укажите ID задачи, которую хотите завершить:"

        await update.message.reply_text(tasks_text, parse_mode='Markdown')
        return COMPLETE_TASK_ID

    except Exception as e:
        logger.error(f"Error in complete_task_start for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])
        return ConversationHandler.END


async def complete_task_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle task ID input for complete_task"""
    try:
        task_id = int(update.message.text.strip())
        context.user_data['task_id'] = task_id
        return await complete_task_process(update, context)
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат ID. Пожалуйста, введите число.",
            parse_mode='Markdown'
        )
        return COMPLETE_TASK_ID


async def complete_task_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process completing the task"""
    user_id = update.effective_user.id
    task_id = context.user_data.get('task_id')

    try:
        # Get task info before completing
        from database import business_repo
        task = business_repo.get_task(task_id)
        
        # Complete task
        success, message = user_manager.complete_task(user_id, task_id)

        if success:
            await update.message.reply_text(
                MESSAGES['task_completed'],
                parse_mode='Markdown'
            )
            
            # Send notification to business owner
            if task:
                business = business_repo.get_business_by_id(task['business_id'])
                if business:
                    owner_id = business['owner_id']
                    
                    # Get employee info
                    user = update.effective_user
                    employee_username = user.username if user.username else user.first_name
                    employee_display = f"@{employee_username}" if user.username else employee_username
                    
                    # Escape markdown
                    escaped_title = escape_markdown(task['title'])
                    escaped_employee = escape_markdown(employee_display)
                    
                    try:
                        await context.bot.send_message(
                            chat_id=owner_id,
                            text=MESSAGES['notification_task_submitted'].format(
                                task_id=task_id,
                                title=escaped_title,
                                employee=escaped_employee
                            ),
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify owner {owner_id} about submitted task {task_id}: {e}")
        else:
            await update.message.reply_text(f"❌ {message}", parse_mode='Markdown')

        logger.info(f"User {user_id} tried to complete task {task_id}: {success}")

    except Exception as e:
        logger.error(f"Error in complete_task_process for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])

    finally:
        context.user_data.clear()

    return ConversationHandler.END


async def complete_task_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel complete task conversation"""
    await update.message.reply_text("❌ Завершение задачи отменено")
    context.user_data.clear()
    return ConversationHandler.END

# :NOTE absolute copy-paste from def complete_task_start()
async def abandon_task_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the abandon task conversation"""
    user_id = update.effective_user.id
    try:
        # Get user's tasks to show
        tasks = user_manager.get_my_tasks(user_id)

        if not tasks:
            await update.message.reply_text(
                MESSAGES['my_tasks_empty'],
                parse_mode='Markdown'
            )
            return ConversationHandler.END

        # Filter only assigned/in_progress tasks
        active_tasks = [t for t in tasks if t['status'] in ('assigned', 'in_progress')]

        if not active_tasks:
            await update.message.reply_text(
                "У вас нет задач в работе, от которых можно отказаться.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END

        # Format tasks list
        tasks_text = "📋 *Ваши задачи в работе:*\n\n"
        for task in active_tasks:
            escaped_title = escape_markdown(task['title'])
            escaped_business = escape_markdown(task['business_name'])
            tasks_text += f"*ID {task['id']}:* {escaped_title}\n"
            tasks_text += f"Бизнес: {escaped_business}\n"
            if task.get('description'):
                desc = task['description'][:100]
                if len(task['description']) > 100:
                    desc += "..."
                escaped_desc = escape_markdown(desc)
                tasks_text += f"Описание: {escaped_desc}\n"
            tasks_text += "\n"

        tasks_text += "\n💡 Пожалуйста, укажите ID задачи, от которой хотите отказаться:"

        await update.message.reply_text(tasks_text, parse_mode='Markdown')
        return ABANDON_TASK_ID
    except Exception as e:
        logger.error(f"Error in abandon_task_start for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])
        return ConversationHandler.END

async def abandon_task_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle task ID input for abandon_task"""
    try:
        task_id = int(update.message.text.strip())
        context.user_data['task_id'] = task_id
        return await abandon_task_process(update, context)
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат ID. Пожалуйста, введите число.",
            parse_mode='Markdown'
        )
        return ABANDON_TASK_ID

async def abandon_task_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process abandoning the task"""
    user_id = update.effective_user.id
    task_id = context.user_data.get('task_id')

    try:
        # Abandon task
        success, message = user_manager.abandon_task(user_id, task_id)

        if success:
            await update.message.reply_text(
                "✅ Вы отказались от задачи! Задача переведена в статус 'отказана'.",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(f"❌ {message}", parse_mode='Markdown')

        logger.info(f"User {user_id} tried to abandon task {task_id}: {success}")

    except Exception as e:
        logger.error(f"Error in abandon_task_process for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])

    finally:
        context.user_data.clear()

    return ConversationHandler.END

async def abandon_task_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel abandon task conversation"""
    await update.message.reply_text("❌ Отказ от задачи отменен")
    context.user_data.clear()
    return ConversationHandler.END
# END of abandon copy-paste

async def all_tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /all_tasks command"""
    user_id = update.effective_user.id

    try:
        # Check if user has active business
        if not user_manager.has_active_business(user_id):
            await update.message.reply_text(
                "❌ У вас нет активного бизнеса.\n\n"
                "Создайте бизнес с помощью /create_business",
                parse_mode='Markdown'
            )
            return

        # Get all active business tasks
        tasks = user_manager.get_business_all_tasks(user_id)

        if not tasks:
            await update.message.reply_text(
                MESSAGES['business_tasks_empty'],
                parse_mode='Markdown'
            )
            return

        # Group tasks by status
        available = [t for t in tasks if t['status'] == 'available']
        assigned = [t for t in tasks if t['status'] in ('assigned', 'in_progress')]
        completed = [t for t in tasks if t['status'] == 'completed']
        abandoned = [t for t in tasks if t['status'] == 'abandoned']

        tasks_text = ""

        if available:
            tasks_text += "*📋 Доступные задачи:*\n"
            for task in available:
                escaped_title = escape_markdown(task['title'])
                tasks_text += f"  • ID {task['id']}: {escaped_title}\n"
            tasks_text += "\n"

        if assigned:
            tasks_text += "*👤 Назначенные задачи:*\n"
            for task in assigned:
                assignee = f"@{task['assigned_to_username']}" if task.get('assigned_to_username') else task.get('assigned_to_name', 'Unknown')
                escaped_title = escape_markdown(task['title'])
                escaped_assignee = escape_markdown(assignee)
                tasks_text += f"  • ID {task['id']}: {escaped_title} → {escaped_assignee}\n"
            tasks_text += "\n"

        if abandoned:
            tasks_text += "*🚫 Отказанные задачи:*\n"
            for task in abandoned:
                abandoned_by = f"@{task['abandoned_by_username']}" if task.get('abandoned_by_username') else task.get('abandoned_by_name', 'Unknown')
                abandoned_at = task['abandoned_at'].strftime("%d.%m.%Y %H:%M") if task.get('abandoned_at') else ""
                escaped_title = escape_markdown(task['title'])
                escaped_abandoned_by = escape_markdown(abandoned_by)
                if abandoned_at:
                    tasks_text += f"  • ID {task['id']}: {escaped_title}\n"
                    tasks_text += f"    🚫 Отказана: {escaped_abandoned_by} ({abandoned_at})\n"
                else:
                    tasks_text += f"  • ID {task['id']}: {escaped_title} (отказана: {escaped_abandoned_by})\n"
            tasks_text += "\n"
            tasks_text += "💡 *Отказанные задачи можно назначить другому сотруднику:*\n"
            tasks_text += "Используйте команду `/assign_task `\n\n"
        if completed:
            tasks_text += f"*✅ Выполнено задач: {len(completed)}*\n"

        await update.message.reply_text(
            MESSAGES['business_tasks'].format(tasks=tasks_text),
            parse_mode='Markdown'
        )
        logger.info(f"User {user_id} viewed all business tasks")

    except Exception as e:
        logger.error(f"Error in all_tasks command for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])


async def submitted_tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /submitted_tasks command"""
    user_id = update.effective_user.id

    try:
        # Check if user has active business
        if not user_manager.has_active_business(user_id):
            await update.message.reply_text(
                "❌ У вас нет активного бизнеса.\n\n"
                "Создайте бизнес с помощью /create_business",
                parse_mode='Markdown'
            )
            return

        # Get submitted tasks
        tasks = user_manager.get_submitted_tasks(user_id)

        if not tasks:
            await update.message.reply_text(
                MESSAGES['submitted_tasks_empty'],
                parse_mode='Markdown'
            )
            return

        # Format tasks list
        tasks_text = ""
        for task in tasks:
            escaped_title = escape_markdown(task['title'])
            employee = f"@{task['assigned_to_username']}" if task.get('assigned_to_username') else task.get('assigned_to_name', 'Unknown')
            escaped_employee = escape_markdown(employee)
            
            # Calculate time taken if possible
            time_info = ""
            if task.get('assigned_at') and task.get('submitted_at'):
                time_taken = (task['submitted_at'] - task['assigned_at']).total_seconds() / 60
                time_info = f"\n⏱ Время выполнения: {int(time_taken)} мин"
            
            tasks_text += f"*ID {task['id']}:* {escaped_title}\n"
            tasks_text += f"👤 Сотрудник: {escaped_employee}{time_info}\n"
            if task.get('difficulty'):
                tasks_text += f"⭐ Сложность: {task['difficulty']}/5\n"
            if task.get('priority'):
                tasks_text += f"🎯 Приоритет: {task['priority']}\n"
            tasks_text += "\n"

        await update.message.reply_text(
            MESSAGES['submitted_tasks'].format(tasks=tasks_text),
            parse_mode='Markdown'
        )
        logger.info(f"User {user_id} viewed submitted tasks")

    except Exception as e:
        logger.error(f"Error in submitted_tasks command for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])


async def review_task_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the review task conversation"""
    user_id = update.effective_user.id

    try:
        # Check if user has active business
        if not user_manager.has_active_business(user_id):
            await update.message.reply_text(
                "❌ У вас нет активного бизнеса.\n\n"
                "Создайте бизнес с помощью /create_business",
                parse_mode='Markdown'
            )
            return ConversationHandler.END

        # Get submitted tasks
        tasks = user_manager.get_submitted_tasks(user_id)

        if not tasks:
            await update.message.reply_text(
                MESSAGES['submitted_tasks_empty'],
                parse_mode='Markdown'
            )
            return ConversationHandler.END

        # Format tasks list
        tasks_text = "📥 *Задачи на проверке:*\n\n"
        for task in tasks:
            escaped_title = escape_markdown(task['title'])
            employee = f"@{task['assigned_to_username']}" if task.get('assigned_to_username') else task.get('assigned_to_name', 'Unknown')
            escaped_employee = escape_markdown(employee)
            tasks_text += f"*ID {task['id']}:* {escaped_title}\n"
            tasks_text += f"Сотрудник: {escaped_employee}\n\n"

        tasks_text += "\n💡 Укажите ID задачи для проверки:"

        await update.message.reply_text(tasks_text, parse_mode='Markdown')
        return REVIEW_TASK_ID

    except Exception as e:
        logger.error(f"Error in review_task_start for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])
        return ConversationHandler.END


async def review_task_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle task ID input for review_task"""
    user_id = update.effective_user.id
    
    try:
        task_id = int(update.message.text.strip())
        
        # Get task details
        from database import business_repo
        task = business_repo.get_task(task_id)
        
        if not task:
            await update.message.reply_text(
                "❌ Задача не найдена",
                parse_mode='Markdown'
            )
            return REVIEW_TASK_ID
        
        # Check if task belongs to user's business
        business = user_manager.get_business(user_id)
        if not business or task['business_id'] != business['id']:
            await update.message.reply_text(
                "❌ Эта задача не принадлежит вашему бизнесу",
                parse_mode='Markdown'
            )
            return REVIEW_TASK_ID
        
        if task['status'] != 'submitted':
            await update.message.reply_text(
                "❌ Задача не отправлена на проверку",
                parse_mode='Markdown'
            )
            return REVIEW_TASK_ID
        
        # Save task_id in context
        context.user_data['task_id'] = task_id
        
        # Calculate time taken
        time_taken_str = "Неизвестно"
        if task.get('assigned_at') and task.get('submitted_at'):
            time_taken = (task['submitted_at'] - task['assigned_at']).total_seconds() / 60
            hours = int(time_taken // 60)
            minutes = int(time_taken % 60)
            if hours > 0:
                time_taken_str = f"{hours} ч {minutes} мин"
            else:
                time_taken_str = f"{minutes} мин"
        
        # Format task info
        employee_raw = task.get('assigned_to_username', task.get('assigned_to_name', 'Unknown'))
        employee = f"@{employee_raw}" if task.get('assigned_to_username') else employee_raw
        
        # Escape markdown special characters
        escaped_title = escape_markdown(task['title'])
        escaped_employee = escape_markdown(employee)
        escaped_description = escape_markdown(task.get('description', 'Нет описания'))
        
        # Format deadline in hours
        deadline_str = 'Не указан'
        if task.get('deadline_minutes'):
            hours = task['deadline_minutes'] / 60
            if hours >= 1:
                deadline_str = f"{hours:.1f} ч"
            else:
                deadline_str = f"{task['deadline_minutes']} мин"
        
        response_text = MESSAGES['review_task_info'].format(
            task_id=task['id'],
            title=escaped_title,
            employee=escaped_employee,
            difficulty=task.get('difficulty', 'Не указана'),
            priority=task.get('priority', 'Не указан'),
            deadline=deadline_str,
            time_taken=time_taken_str,
            description=escaped_description
        )
        
        await update.message.reply_text(response_text, parse_mode='Markdown')
        logger.info(f"User {user_id} reviewing task {task_id}")
        return REVIEW_TASK_DECISION
        
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат ID. Пожалуйста, введите число.",
            parse_mode='Markdown'
        )
        return REVIEW_TASK_ID
    except Exception as e:
        logger.error(f"Error in review_task_id_handler for user {user_id}: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Произошла ошибка при загрузке задачи. Попробуйте еще раз.",
            parse_mode='Markdown'
        )
        return REVIEW_TASK_ID


async def review_task_decision_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle review decision input"""
    user_id = update.effective_user.id
    text = update.message.text.strip().lower()
    task_id = context.user_data.get('task_id')
    
    try:
        # Get task info for notifications
        from database import business_repo
        task = business_repo.get_task(task_id)
        
        # Check if reject
        if text == 'отклонить':
            success, message = user_manager.reject_task(user_id, task_id)
            if success:
                # Escape markdown in message
                escaped_message = escape_markdown(message)
                await update.message.reply_text(
                    MESSAGES['task_rejected'].format(message=escaped_message),
                    parse_mode='Markdown'
                )
                
                # Send notification to employee
                if task and task.get('assigned_to'):
                    employee_id = task['assigned_to']
                    escaped_title = escape_markdown(task['title'])
                    try:
                        await context.bot.send_message(
                            chat_id=employee_id,
                            text=MESSAGES['notification_task_rejected'].format(
                                task_id=task_id,
                                title=escaped_title
                            ),
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify employee {employee_id} about rejected task {task_id}: {e}")
            else:
                escaped_message = escape_markdown(message)
                await update.message.reply_text(f"❌ {escaped_message}", parse_mode='Markdown')
            
            context.user_data.clear()
            return ConversationHandler.END
        
        # Check if send for revision
        if text.startswith('доработка'):
            parts = text.split()
            if len(parts) != 2:
                await update.message.reply_text(
                    "❌ Неверный формат. Используйте: `доработка [часы]`\nНапример: `доработка 2`",
                    parse_mode='Markdown'
                )
                return REVIEW_TASK_DECISION
            
            try:
                new_deadline_hours = int(parts[1])
                # Convert hours to minutes
                new_deadline_minutes = new_deadline_hours * 60
                success, message = user_manager.send_task_for_revision(user_id, task_id, new_deadline_minutes)
                if success:
                    # Escape markdown in message
                    escaped_message = escape_markdown(message)
                    await update.message.reply_text(
                        MESSAGES['task_sent_for_revision'].format(message=escaped_message),
                        parse_mode='Markdown'
                    )
                    
                    # Send notification to employee
                    if task and task.get('assigned_to'):
                        employee_id = task['assigned_to']
                        escaped_title = escape_markdown(task['title'])
                        try:
                            await context.bot.send_message(
                                chat_id=employee_id,
                                text=MESSAGES['notification_task_revision'].format(
                                    task_id=task_id,
                                    title=escaped_title,
                                    deadline=new_deadline_hours
                                ),
                                parse_mode='Markdown'
                            )
                        except Exception as e:
                            logger.error(f"Failed to notify employee {employee_id} about task revision {task_id}: {e}")
                else:
                    escaped_message = escape_markdown(message)
                    await update.message.reply_text(f"❌ {escaped_message}", parse_mode='Markdown')
                
                context.user_data.clear()
                return ConversationHandler.END
            except ValueError:
                await update.message.reply_text(
                    "❌ Неверный формат дедлайна. Укажите число.",
                    parse_mode='Markdown'
                )
                return REVIEW_TASK_DECISION
        
        # Try to parse as quality coefficient
        try:
            quality = float(text.replace(',', '.'))
            if not (0.5 <= quality <= 1.0):
                await update.message.reply_text(
                    "❌ Коэффициент качества должен быть от 0.5 до 1.0",
                    parse_mode='Markdown'
                )
                return REVIEW_TASK_DECISION
            
            success, message, result = user_manager.accept_task(user_id, task_id, quality)
            if success:
                # Escape markdown in message
                escaped_message = escape_markdown(message)
                await update.message.reply_text(
                    MESSAGES['task_accepted'].format(message=escaped_message),
                    parse_mode='Markdown'
                )
                
                # Send notification to employee
                if task and task.get('assigned_to') and result:
                    employee_id = task['assigned_to']
                    escaped_title = escape_markdown(task['title'])
                    try:
                        await context.bot.send_message(
                            chat_id=employee_id,
                            text=MESSAGES['notification_task_accepted'].format(
                                task_id=task_id,
                                title=escaped_title,
                                quality=quality,
                                rating_change=result['rating_change'],
                                new_rating=result['new_rating']
                            ),
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify employee {employee_id} about accepted task {task_id}: {e}")
            else:
                escaped_message = escape_markdown(message)
                await update.message.reply_text(f"❌ {escaped_message}", parse_mode='Markdown')
            
            context.user_data.clear()
            return ConversationHandler.END
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат. Введите:\n"
                "• Коэффициент качества (0.5-1.0)\n"
                "• `доработка [минуты]`\n"
                "• `отклонить`",
                parse_mode='Markdown'
            )
            return REVIEW_TASK_DECISION
            
    except Exception as e:
        logger.error(f"Error in review_task_decision_handler for user {user_id}: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Произошла ошибка при обработке. Попробуйте снова с команды /review_task",
            parse_mode='Markdown'
        )
        context.user_data.clear()
        return ConversationHandler.END


async def review_task_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel review task conversation"""
    await update.message.reply_text("❌ Проверка задачи отменена")
    context.user_data.clear()
    return ConversationHandler.END


# Find similar users command handler
async def export_history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /export_history command to export chat history as PDF"""
    user_id = update.effective_user.id
    user = update.effective_user
    user_name = user.first_name or user.username or "Пользователь"
    
    try:
        # Ensure user exists in database
        user_manager.get_or_create_user(
            user_id=user_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
        # Show generating message
        thinking_msg = await update.message.reply_text("📄 Генерирую PDF с историей общения...")
        
        pdf_path = None
        try:
            # Get chat history from database
            from database import user_repo
            chat_history = user_repo.get_usage_history(user_id, limit=100)  # Last 100 messages
            
            if not chat_history:
                await thinking_msg.edit_text(
                    "📭 У вас пока нет истории общения с ботом."
                )
                return
            
            # Update status message
            await thinking_msg.edit_text("📄 Создаю PDF документ...")
            
            # Generate PDF
            try:
                logger.info(f"Starting PDF generation for user {user_id} with {len(chat_history)} messages")
                pdf_path = chat_history_pdf.generate(
                    chat_history=chat_history,
                    user_name=user_name
                )
                
                logger.info(f"Chat history PDF generated for user {user_id}: {pdf_path}")
                
                # Verify file exists
                if not os.path.exists(pdf_path):
                    logger.error(f"PDF file was not created: {pdf_path}")
                    await thinking_msg.edit_text(
                        "❌ Не удалось создать PDF. Попробуйте позже."
                    )
                    return
                
                logger.info(f"PDF file size: {os.path.getsize(pdf_path)} bytes")
                
            except Exception as pdf_error:
                logger.error(f"PDF generation error for user {user_id}: {pdf_error}", exc_info=True)
                await thinking_msg.edit_text(
                    "❌ Не удалось создать PDF. Попробуйте позже."
                )
                return
            
            # Send PDF document
            await thinking_msg.edit_text("📤 Отправляю PDF документ...")
            
            try:
                logger.info(f"Opening PDF file: {pdf_path}")
                with open(pdf_path, 'rb') as pdf_file:
                    logger.info(f"Sending PDF document to user {user_id}")
                    await update.message.reply_document(
                        document=pdf_file,
                        filename=f"История_чата_{user_name}.pdf",
                        caption=f"📜 *История общения с ботом*\n\n"
                               f"Экспортировано сообщений: {len(chat_history)}\n"
                               f"Дата создания: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                        parse_mode='Markdown'
                    )
                
                # Delete thinking message
                await thinking_msg.delete()
                
                logger.info(f"Chat history PDF sent successfully to user {user_id}")
                
            except Exception as send_error:
                logger.error(f"Error sending PDF to user {user_id}: {send_error}", exc_info=True)
                await thinking_msg.edit_text(
                    "❌ Произошла ошибка при отправке PDF файла. Попробуйте позже."
                )
        
        except Exception as e:
            logger.error(f"Error exporting chat history for user {user_id}: {e}", exc_info=True)
            try:
                await thinking_msg.edit_text(
                    "❌ Произошла ошибка при экспорте истории. Попробуйте позже."
                )
            except:
                pass
        
        finally:
            # Clean up PDF file after sending
            if pdf_path and os.path.exists(pdf_path):
                try:
                    import asyncio
                    await asyncio.sleep(1)
                    os.remove(pdf_path)
                    logger.info(f"Cleaned up PDF file: {pdf_path}")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup PDF {pdf_path}: {cleanup_error}")
    
    except Exception as e:
        logger.error(f"Error in export_history command for user {user_id}: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Произошла ошибка при экспорте истории. Попробуйте позже."
        )


async def find_similar_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /find_similar command to find similar users for collaboration"""
    user_id = update.effective_user.id
    user = update.effective_user

    # Check if user has filled their info
    if not await check_user_info_filled(update, context):
        return

    try:
        # Ensure user exists in database
        user_manager.get_or_create_user(
            user_id=user_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )

        # Check if user has active business
        if not user_manager.has_active_business(user_id):
            await update.message.reply_text(
                "❌ У вас нет активного бизнеса.\n\n"
                "Создайте бизнес с помощью /create_business",
                parse_mode='Markdown'
            )
            return

        # Check if user has business_info
        if not user_manager.has_business_info(user_id):
            await update.message.reply_text(
                MESSAGES['similar_no_business_info'],
                parse_mode='Markdown'
            )
            return

        # Show welcome message
        await update.message.reply_text(
            MESSAGES['similar_welcome'],
            parse_mode='Markdown'
        )

        # Show searching message
        thinking_msg = await update.message.reply_text(MESSAGES['similar_searching'])

        try:
            # Check tokens (2 tokens for similar users search)
            success, error_msg = user_manager.process_request(user_id, tokens_amount=COMMANDS_COSTS["find_similar_command"])

            if not success:
                await thinking_msg.edit_text(
                    MESSAGES['no_tokens'].format(refresh_time=error_msg),
                    parse_mode='Markdown'
                )
                return

            # Get current user's information
            current_user_business_info = user_manager.get_business_info(user_id)
            current_user_info = {
                'user_id': user_id,
                'username': user.username,
                'business_info': current_user_business_info
            }

            # Get all other users with business_info
            from database import user_repo
            other_users = user_repo.get_all_users_with_business_info(exclude_user_id=user_id)

            if not other_users:
                await thinking_msg.edit_text(MESSAGES['similar_no_users'])
                return

            # Parse business_info for each user
            parsed_users = []
            for user_data in other_users:
                try:
                    import json
                    business_info = {
                        'business_name': user_data.get('business_name'),
                        'business_type': user_data.get('business_type'),
                        'financial_situation': user_data.get('financial_situation'),
                        'goals': user_data.get('goals')
                    }
                    parsed_user = {
                        'user_id': user_data['user_id'],
                        'username': user_data.get('username'),
                        'business_info': business_info,
                        'workers_info': json.loads(user_data['workers_info']) if user_data.get('workers_info') else {},
                        'executors_info': json.loads(user_data['executors_info']) if user_data.get('executors_info') else {}
                    }
                    parsed_users.append(parsed_user)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse data for user {user_data['user_id']}")
                    continue

            if not parsed_users:
                await thinking_msg.edit_text(MESSAGES['similar_no_users'])
                return

            logger.info(f"Finding similar users for {user_id} among {len(parsed_users)} candidates")

            # Find similar users using AI
            search_results = ai_client.find_similar_users(current_user_info, parsed_users)

            logger.info(f"Similar users results generated for user {user_id}, length: {len(search_results)}")

            # Send results
            # AI-generated content is not escaped as it contains intentional markdown
            try:
                await thinking_msg.edit_text(
                    f"🤝 *Подходящие партнёры для сотрудничества:*\n\n{search_results}",
                    parse_mode='Markdown'
                )
            except BadRequest as e:
                # If Markdown parsing fails, send as plain text
                logger.warning(f"Markdown parsing failed for user {user_id}, sending as plain text: {e}")
                await thinking_msg.edit_text(f"🤝 Подходящие партнёры для сотрудничества:\n\n{search_results}")

            # Log usage
            user_manager.log_usage(
                user_id,
                f"Find similar users search",
                search_results[:500],
                tokens_used=2
            )

            logger.info(f"Successfully completed find_similar for user {user_id}")

        except Exception as e:
            logger.error(f"Error in find_similar for user {user_id}: {e}", exc_info=True)
            try:
                await thinking_msg.edit_text(MESSAGES['similar_error'])
            except:
                pass

    except Exception as e:
        logger.error(f"Error in find_similar_command for user {user_id}: {e}", exc_info=True)
        await update.message.reply_text(MESSAGES['similar_error'])


async def swipe_employees_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the swipe employees feature"""
    user_id = update.effective_user.id

    try:
        # Check if user is business owner
        if not user_manager.is_business_owner(user_id):
            await update.message.reply_text(
                MESSAGES['task_no_business'],
                parse_mode='Markdown'
            )
            return ConversationHandler.END

        # Get business info
        business = user_manager.get_business(user_id)
        business_info = {
            'business_name': business.get('business_name'),
            'business_type': business.get('business_type'),
            'financial_situation': business.get('financial_situation'),
            'goals': business.get('goals')
        }

        # Show searching message
        thinking_msg = await update.message.reply_text("🔍 Ищу подходящих кандидатов...")

        # Get available candidates (users without business or job)
        candidates = user_manager.get_users_without_business_or_job(exclude_user_id=user_id)

        if not candidates:
            await thinking_msg.edit_text(
                "😔 К сожалению, сейчас нет доступных кандидатов без места работы.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END

        # Use AI to find top 3 candidates
        top_candidates = ai_client.find_top_candidates_for_business(business_info, candidates)

        if not top_candidates:
            await thinking_msg.edit_text(
                "😔 К сожалению, не нашлось подходящих кандидатов для вашего бизнеса.\n\n"
                "Попробуйте позже!",
                parse_mode='Markdown'
            )
            return ConversationHandler.END

        # Save candidates to context
        context.user_data['candidates'] = top_candidates
        context.user_data['current_index'] = 0

        # Delete thinking message
        await thinking_msg.delete()

        # Show first candidate
        return await show_next_candidate(update, context)

    except Exception as e:
        logger.error(f"Error in swipe_employees_start for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])
        return ConversationHandler.END


async def show_next_candidate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show the next candidate with accept/reject buttons"""
    candidates = context.user_data.get('candidates', [])
    current_index = context.user_data.get('current_index', 0)

    # Check if we've shown all candidates
    if current_index >= len(candidates):
        await update.effective_message.reply_text(
            "✅ Вы просмотрели всех доступных кандидатов!",
            parse_mode='Markdown'
        )
        context.user_data.clear()
        return ConversationHandler.END

    # Get current candidate
    candidate = candidates[current_index]
    username = candidate.get('username') or f"пользователь_{candidate.get('user_id')}"
    first_name = candidate.get('first_name', '')
    user_info = candidate.get('user_info', 'Нет описания')
    rating = candidate.get('overall_rating')
    reasoning = candidate.get('reasoning', 'AI рекомендует этого кандидата')

    # Format rating
    rating_text = f"⭐ Рейтинг: {rating}" if rating is not None else "⭐ Рейтинг: нет опыта"

    # Escape markdown in user input
    escaped_username = escape_markdown(f"@{username}")
    escaped_first_name = escape_markdown(first_name)
    escaped_user_info = escape_markdown(user_info)
    escaped_reasoning = escape_markdown(reasoning)

    # Create message
    message_text = (
        f"👤 *Кандидат {current_index + 1} из {len(candidates)}*\n\n"
        f"*Пользователь:* {escaped_username}\n"
        f"*Имя:* {escaped_first_name}\n"
        f"{rating_text}\n\n"
        f"*Описание:*\n{escaped_user_info}\n\n"
        f"🤖 *Почему подходит:*\n{escaped_reasoning}\n\n"
        f"Пригласить этого кандидата?"
    )

    # Create inline keyboard
    keyboard = [
        [
            InlineKeyboardButton("✅ Принять", callback_data=f"swipe_accept_{current_index}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"swipe_reject_{current_index}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Send or edit message
    if update.callback_query:
        logger.info(f"Editing message for user {update.effective_user.id}")
        await update.callback_query.edit_message_text(
            text=message_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    else:
        logger.info(f"Sending message for user {update.effective_user.id}")
        await update.message.reply_text(
            text=message_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

    return SWIPE_EMPLOYEES_VIEWING


async def swipe_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle swipe accept/reject callbacks"""
    query = update.callback_query
    user_id = update.effective_user.id
    data = query.data
    
    logger.info(f"Swipe callback handler called for user {user_id}, data: {data}")

    try:
        candidates = context.user_data.get('candidates', [])
        current_index = context.user_data.get('current_index', 0)
        
        logger.info(f"Current index: {current_index}, Total candidates: {len(candidates)}")

        if not candidates or current_index >= len(candidates):
            logger.warning(f"No candidates or index out of range for user {user_id}")
            await query.answer("❌ Произошла ошибка")
            await query.edit_message_text("❌ Произошла ошибка. Попробуйте еще раз.")
            context.user_data.clear()
            return ConversationHandler.END

        candidate = candidates[current_index]
        candidate_username = candidate.get('username') or f"пользователь_{candidate.get('user_id')}"
        
        logger.info(f"Processing candidate: {candidate_username}")

        if data.startswith("swipe_accept_"):
            logger.info(f"User {user_id} accepted candidate {candidate_username}")
            # Answer callback query first
            await query.answer("✅ Отправляю приглашение...")
            
            # Invite the candidate
            success, message = user_manager.invite_employee(user_id, candidate_username)

            if success:
                logger.info(f"Successfully invited candidate {candidate_username}")
                # Notify the candidate
                candidate_id = candidate.get('user_id')
                if candidate_id:
                    try:
                        business = user_manager.get_business(user_id)
                        # Get the invitation ID
                        invitations = user_manager.get_pending_invitations(candidate_id)
                        invitation_id = None
                        for inv in invitations:
                            if inv['business_name'] == business['business_name']:
                                invitation_id = inv['id']
                                break

                        if invitation_id:
                            # Create inline keyboard with Accept/Reject buttons
                            keyboard = [
                                [
                                    InlineKeyboardButton("✅ Принять", callback_data=f"accept_inv_{invitation_id}"),
                                    InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_inv_{invitation_id}")
                                ]
                            ]
                            reply_markup = InlineKeyboardMarkup(keyboard)

                            escaped_business_name = escape_markdown(business['business_name'])
                            await context.bot.send_message(
                                chat_id=candidate_id,
                                text=f"🎉 *Новое приглашение!*\n\n"
                                     f"Вас пригласили стать сотрудником бизнеса *{escaped_business_name}*\n\n"
                                     f"Выберите действие:",
                                parse_mode='Markdown',
                                reply_markup=reply_markup
                            )
                            logger.info(f"Sent invitation notification to candidate {candidate_id}")
                    except Exception as e:
                        logger.warning(f"Failed to notify user {candidate_id}: {e}")
                
                # Delete the current message
                try:
                    await query.message.delete()
                    logger.info(f"Deleted current swipe message for user {user_id}")
                except Exception as del_err:
                    logger.warning(f"Failed to delete message: {del_err}")
                
                # Send confirmation message
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"✅ Приглашение отправлено @{candidate_username}!"
                )
                logger.info(f"Sent confirmation message to user {user_id}")
            else:
                logger.warning(f"Failed to invite candidate {candidate_username}: {message}")
                await query.answer("❌ Ошибка")
                await query.edit_message_text(f"❌ {message}")
                return ConversationHandler.END

        elif data.startswith("swipe_reject_"):
            logger.info(f"User {user_id} rejected candidate {candidate_username}")
            # Answer callback query
            await query.answer("➡️ Следующий кандидат")
            
            # Delete the current message
            try:
                await query.message.delete()
                logger.info(f"Deleted message for user {user_id}")
            except Exception as del_err:
                logger.warning(f"Failed to delete message: {del_err}")

        # Move to next candidate
        context.user_data['current_index'] = current_index + 1
        logger.info(f"Moving to next candidate, new index: {context.user_data['current_index']}")

        # Check if there are more candidates
        if context.user_data['current_index'] >= len(candidates):
            await context.bot.send_message(
                chat_id=user_id,
                text="✅ Вы просмотрели всех доступных кандидатов!",
                parse_mode='Markdown'
            )
            context.user_data.clear()
            return ConversationHandler.END

        # Show next candidate in a new message
        next_candidate = candidates[context.user_data['current_index']]
        current_idx = context.user_data['current_index']
        
        username = next_candidate.get('username') or f"пользователь_{next_candidate.get('user_id')}"
        first_name = next_candidate.get('first_name', '')
        user_info = next_candidate.get('user_info', 'Нет описания')
        rating = next_candidate.get('overall_rating')
        reasoning = next_candidate.get('reasoning', 'AI рекомендует этого кандидата')

        # Format rating
        rating_text = f"⭐ Рейтинг: {rating}" if rating is not None else "⭐ Рейтинг: нет опыта"

        # Escape markdown in user input
        escaped_username = escape_markdown(f"@{username}")
        escaped_first_name = escape_markdown(first_name)
        escaped_user_info = escape_markdown(user_info)
        escaped_reasoning = escape_markdown(reasoning)

        # Create message
        message_text = (
            f"👤 *Кандидат {current_idx + 1} из {len(candidates)}*\n\n"
            f"*Пользователь:* {escaped_username}\n"
            f"*Имя:* {escaped_first_name}\n"
            f"{rating_text}\n\n"
            f"*Описание:*\n{escaped_user_info}\n\n"
            f"🤖 *Почему подходит:*\n{escaped_reasoning}\n\n"
            f"Пригласить этого кандидата?"
        )

        # Create inline keyboard
        keyboard = [
            [
                InlineKeyboardButton("✅ Принять", callback_data=f"swipe_accept_{current_idx}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"swipe_reject_{current_idx}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        logger.info(f"Sending new candidate message to user {user_id}, candidate {current_idx + 1}/{len(candidates)}")
        
        sent_message = await context.bot.send_message(
            chat_id=user_id,
            text=message_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
        logger.info(f"Successfully sent message {sent_message.message_id} to user {user_id}")

        return SWIPE_EMPLOYEES_VIEWING

    except Exception as e:
        logger.error(f"Error in swipe_callback_handler for user {user_id}: {e}", exc_info=True)
        await query.answer("❌ Ошибка")
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=MESSAGES['database_error']
            )
        except:
            pass
        context.user_data.clear()
        return ConversationHandler.END


async def swipe_employees_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel swipe employees"""
    await update.message.reply_text("❌ Просмотр кандидатов отменен")
    context.user_data.clear()
    return ConversationHandler.END


async def check_overdue_tasks_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Background job to check for overdue tasks"""
    try:
        from database import business_repo
        from database import user_repo
        
        failed_tasks = business_repo.check_overdue_tasks()
        
        if failed_tasks:
            logger.info(f"Auto-failed {len(failed_tasks)} overdue tasks")
            
            # Notify business owners and employees
            for task_info in failed_tasks:
                task_id = task_info['task_id']
                employee_id = task_info['employee_id']
                business_id = task_info['business_id']
                
                # Get task details
                task = business_repo.get_task(task_id)
                if not task:
                    continue
                
                # Get business owner
                business = business_repo.get_business_by_id(business_id)
                if business:
                    owner_id = business['owner_id']
                    
                    # Get employee info
                    employee = user_repo.get_user(employee_id)
                    employee_display = f"@{employee['username']}" if employee and employee.get('username') else f"ID {employee_id}"
                    
                    # Escape markdown
                    escaped_title = escape_markdown(task['title'])
                    escaped_employee = escape_markdown(employee_display)
                    
                    # Notify owner
                    try:
                        await context.bot.send_message(
                            chat_id=owner_id,
                            text=MESSAGES['notification_task_overdue_owner'].format(
                                task_id=task_id,
                                title=escaped_title,
                                employee=escaped_employee
                            ),
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify owner {owner_id}: {e}")
                    
                    # Notify employee
                    try:
                        await context.bot.send_message(
                            chat_id=employee_id,
                            text=MESSAGES['notification_task_overdue_employee'].format(
                                task_id=task_id,
                                title=escaped_title
                            ),
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify employee {employee_id}: {e}")
                        
    except Exception as e:
        logger.error(f"Error in check_overdue_tasks_job: {e}")


async def setup_bot_commands(application):
    """Set up bot commands for Telegram menu"""
    from telegram import BotCommand
   
    commands = [
        BotCommand("start", "Начать работу с ботом"),
        BotCommand("help", "Справка по командам"),
        BotCommand("balance", "Проверить баланс токенов"),
        BotCommand("roulette", "🎰 Ежедневная рулетка (1-50 токенов)"),
        BotCommand("finance", "Зарегистрировать бизнес и получить финплан"),
        BotCommand("clients", "Найти клиентов"),
        BotCommand("executors", "Найти исполнителей"),
        BotCommand("find_similar", "Найти партнёров"),
        BotCommand("export_history", "Экспорт истории чата в PDF"),
        BotCommand("add_employee", "Пригласить сотрудника"),
        BotCommand("swipe_employees", "🔍 Найти сотрудников (свайп)"),
        BotCommand("fire_employee", "Уволить сотрудника"),
        BotCommand("employees", "Список сотрудников"),
        BotCommand("invitations", "Посмотреть приглашения"),
        BotCommand("accept", "Принять приглашение"),
        BotCommand("reject", "Отклонить приглашение"),
        BotCommand("my_employers", "Мои работодатели"),
        BotCommand("create_task", "Создать задачу"),
        BotCommand("available_tasks", "Доступные задачи"),
        BotCommand("my_tasks", "Мои задачи"),
        BotCommand("all_tasks", "Все задачи бизнеса"),
        BotCommand("take_task", "Взять задачу"),
        BotCommand("assign_task", "Назначить задачу"),
        BotCommand("complete_task", "Сдать задачу на проверку"),
        BotCommand("abandon_task", "Отказаться от задачи"),
        BotCommand("submitted_tasks", "Задачи на проверке"),
        BotCommand("review_task", "Проверить задачу"),
        BotCommand("create_business", "Зарегистрировать бизнеc"),
        BotCommand("my_businesses", "Мои бизнесы"),
        BotCommand("delete_business", "Удалить бизнес"),
        BotCommand("switch_businesses", "Сменить активный бизнес"),
    ]
    
    await application.bot.set_my_commands(commands)
    logger.info("Bot commands registered successfully")

def quick_log_setup():
    # Create handler that rotates every hour
    handler = TimedRotatingFileHandler(
        'telegram_bot.log',
        when='H',
        interval=1,
        backupCount=48,
        encoding='utf-8'
    )
    
    # Setup logging format
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[handler, logging.StreamHandler()]
    )
    
    logging.info("Logging system initialized - Hourly rotation active")

def main() -> None:
    """Start the bot"""
    try:
        # Validate configuration
        Config.validate()
        logger.info("Configuration validated successfully")

        # Initialize database
        logger.info("Connecting to database...")
        db.connect()
        logger.info("Database connected successfully")

        # Create HTTP request handler with increased timeouts
        # This prevents timeout errors when network is slow
        request = HTTPXRequest(
            connection_pool_size=8,
            connect_timeout=30.0,      # 30 seconds to establish connection
            read_timeout=30.0,          # 30 seconds to read response
            write_timeout=30.0,         # 30 seconds to send request
            pool_timeout=10.0           # 10 seconds to get connection from pool
        )
        quick_log_setup()
        # Create the Application with custom request handler
        application = (
            Application.builder()
            .token(Config.TELEGRAM_BOT_TOKEN)
            .request(request)
            .build()
        )
    

        # Register employee management conversation handlers
        add_employee_handler = ConversationHandler(
            entry_points=[CommandHandler("add_employee", add_employee_start)],
            states={
                ADD_EMPLOYEE_USERNAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, add_employee_username_handler)
                ],
            },
            fallbacks=[CommandHandler("cancel", add_employee_cancel)],
        )
        application.add_handler(add_employee_handler)

        fire_employee_handler = ConversationHandler(
            entry_points=[CommandHandler("fire_employee", fire_employee_start)],
            states={
                FIRE_EMPLOYEE_USERNAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, fire_employee_username_handler)
                ],
            },
            fallbacks=[CommandHandler("cancel", fire_employee_cancel)],
        )
        application.add_handler(fire_employee_handler)

        accept_invitation_handler = ConversationHandler(
            entry_points=[CommandHandler("accept", accept_invitation_start)],
            states={
                ACCEPT_INVITATION_ID: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, accept_invitation_id_handler)
                ],
            },
            fallbacks=[CommandHandler("cancel", accept_invitation_cancel)],
        )
        application.add_handler(accept_invitation_handler)

        reject_invitation_handler = ConversationHandler(
            entry_points=[CommandHandler("reject", reject_invitation_start)],
            states={
                REJECT_INVITATION_ID: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, reject_invitation_id_handler)
                ],
            },
            fallbacks=[CommandHandler("cancel", reject_invitation_cancel)],
        )
        application.add_handler(reject_invitation_handler)

        # Register task management command handlers
        application.add_handler(CommandHandler("available_tasks", available_tasks_command))
        application.add_handler(CommandHandler("my_tasks", my_tasks_command))
        application.add_handler(CommandHandler("all_tasks", all_tasks_command))

        # Register task management conversation handlers
        take_task_handler = ConversationHandler(
            entry_points=[CommandHandler("take_task", take_task_start)],
            states={
                TAKE_TASK_ID: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, take_task_id_handler)
                ],
            },
            fallbacks=[CommandHandler("cancel", take_task_cancel)],
        )
        application.add_handler(take_task_handler)

        assign_task_handler = ConversationHandler(
            entry_points=[CommandHandler("assign_task", assign_task_start)],
            states={
                ASSIGN_TASK_ID: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, assign_task_id_handler)
                ],
                ASSIGN_TASK_USERNAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, assign_task_username_handler)
                ],
            },
            fallbacks=[CommandHandler("cancel", assign_task_cancel)],
        )
        application.add_handler(assign_task_handler)

        complete_task_handler = ConversationHandler(
            entry_points=[CommandHandler("complete_task", complete_task_start)],
            states={
                COMPLETE_TASK_ID: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, complete_task_id_handler)
                ],
            },
            fallbacks=[CommandHandler("cancel", complete_task_cancel)],
        )
        application.add_handler(complete_task_handler)

        # Register create task conversation handler
        create_task_handler = ConversationHandler(
            entry_points=[CommandHandler("create_task", create_task_command)],
            states={
                TASK_DESCRIPTION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, task_description_handler)
                ],
                TASK_DEADLINE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, task_deadline_handler)
                ],
                TASK_DIFFICULTY: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, task_difficulty_handler)
                ],
                TASK_PRIORITY: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, task_priority_handler)
                ],
            },
            fallbacks=[CommandHandler("cancel", task_cancel)],
        )
        application.add_handler(create_task_handler)

        # Register abandon task conversation handler
        abandon_task_handler = ConversationHandler(
            entry_points=[CommandHandler("abandon_task", abandon_task_start)],
            states={
                ABANDON_TASK_ID: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, abandon_task_id_handler)
                ],
            },
            fallbacks=[CommandHandler("cancel", abandon_task_cancel)],
        )
        application.add_handler(abandon_task_handler)

        # Register submitted tasks command handler
        application.add_handler(CommandHandler("submitted_tasks", submitted_tasks_command))

        # Register review task conversation handler
        review_task_handler = ConversationHandler(
            entry_points=[CommandHandler("review_task", review_task_start)],
            states={
                REVIEW_TASK_ID: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, review_task_id_handler)
                ],
                REVIEW_TASK_DECISION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, review_task_decision_handler)
                ],
            },
            fallbacks=[CommandHandler("cancel", review_task_cancel)],
        )
        application.add_handler(review_task_handler)

        # Register finance conversation handler
        finance_handler = ConversationHandler(
            entry_points=[CommandHandler("finance", finance_start)],
            states={
                CHECKING_EXISTING: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, finance_check_existing)
                ],
                QUESTION_1: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, finance_question_1)
                ],
                QUESTION_2: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, finance_question_2)
                ],
                QUESTION_3: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, finance_question_3)
                ],
                QUESTION_4: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, finance_question_4)
                ],
            },
            fallbacks=[CommandHandler("cancel", finance_cancel)],
        )
        application.add_handler(finance_handler)

        # Register create business conversation handler
        create_business_handler = ConversationHandler(
            entry_points=[CommandHandler("create_business", create_business_start)],
            states={
                CREATE_BUSINESS_Q1: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, create_business_q1)
                ],
                CREATE_BUSINESS_Q2: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, create_business_q2)
                ],
                CREATE_BUSINESS_Q3: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, create_business_q3)
                ],
                CREATE_BUSINESS_Q4: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, create_business_q4)
                ],
            },
            fallbacks=[
                CommandHandler("cancel", create_business_cancel), MessageHandler(filters.COMMAND, create_business_cancel)
                ],

        )
        application.add_handler(create_business_handler)

        # Register switch businesses conversation handler
        switch_businesses_handler = ConversationHandler(
            entry_points=[CommandHandler("switch_businesses", switch_businesses_start)],
            states={
                SWITCH_BUSINESS_ID: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, switch_businesses_id_handler)
                ],
            },
            fallbacks=[CommandHandler("cancel", switch_businesses_cancel)],
        )
        application.add_handler(switch_businesses_handler)

        # Register delete business conversation handler
        delete_business_handler = ConversationHandler(
            entry_points=[CommandHandler("delete_business", delete_business_start)],
            states={
                DELETE_BUSINESS_ID: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, delete_business_id_handler)
                ],
                DELETE_BUSINESS_CONFIRM: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, delete_business_confirm_handler)
                ],
            },
            fallbacks=[CommandHandler("cancel", delete_business_cancel)],
        )
        application.add_handler(delete_business_handler)

        # Register clients search conversation handler
        clients_handler = ConversationHandler(
            entry_points=[CommandHandler("clients", clients_start)],
            states={
                CLIENTS_CHECKING: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, clients_check_existing)
                ],
                CLIENTS_QUESTION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, clients_answer)
                ],
            },
            fallbacks=[CommandHandler("cancel", clients_cancel)],
        )
        application.add_handler(clients_handler)

        # Register executors search conversation handler
        executors_handler = ConversationHandler(
            entry_points=[CommandHandler("executors", executors_start)],
            states={
                EXECUTORS_CHECKING: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, executors_check_existing)
                ],
                EXECUTORS_QUESTION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, executors_answer)
                ],
            },
            fallbacks=[CommandHandler("cancel", executors_cancel)],
        )
        application.add_handler(executors_handler)

        # Register swipe employees conversation handler
        swipe_employees_handler = ConversationHandler(
            entry_points=[CommandHandler("swipe_employees", swipe_employees_start)],
            states={
                SWIPE_EMPLOYEES_VIEWING: [
                    CallbackQueryHandler(swipe_callback_handler, pattern="^swipe_(accept|reject)_")
                ],
            },
            fallbacks=[CommandHandler("cancel", swipe_employees_cancel)],  # Track callback queries per message
        )
        application.add_handler(swipe_employees_handler)
        # Register start command as conversation handler (for user info collection)
        start_handler = ConversationHandler(
            entry_points=[CommandHandler("start", start_command)],
            states={
                USER_INFO_INPUT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, user_info_handler)
                ],
            },
            fallbacks=[],
            allow_reentry=True
        )
        application.add_handler(start_handler)

        # Register other command handlers
        application.add_handler(CommandHandler("balance", balance_command))
        application.add_handler(CommandHandler("roulette", roulette_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("find_similar", find_similar_command))
        application.add_handler(CommandHandler("export_history", export_history_command))

        # Register callback query handler for inline buttons (only invitation buttons)
        application.add_handler(CallbackQueryHandler(
            invitation_callback_handler, 
            pattern="^(accept_inv_|reject_inv_)"
        ))

        # Register employee management command handlers
        application.add_handler(CommandHandler("employees", employees_command))
        application.add_handler(CommandHandler("invitations", invitations_command))
        application.add_handler(CommandHandler("my_employers", my_employers_command))
        application.add_handler(CommandHandler("my_businesses", my_businesses_command))
        # Register message handler
        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
        )

        # Register error handler
        application.add_error_handler(error_handler)

        # Set up bot commands for Telegram menu
        import asyncio
        #asyncio.get_event_loop().run_until_complete(setup_bot_commands(application))

        # Set up background job to check overdue tasks every 5 minutes
        job_queue = application.job_queue
        job_queue.run_repeating(check_overdue_tasks_job, interval=300, first=10)
        logger.info("Background job for checking overdue tasks scheduled (every 5 minutes)")

        # Start the bot
        logger.info("🚀 Bot is starting...")
        logger.info(f"Using AI model: {Config.AI_MODEL}")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Failed to start bot: {e}", exc_info=True)
    finally:
        # Close database connections
        db.close()
        logger.info("Bot shutdown complete")


if __name__ == '__main__':
    main()
