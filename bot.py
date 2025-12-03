"""
Telegram bot with AI integration, user accounts, and token system
"""
import os
import logging
import re
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
from pdf_generator import pdf_generator

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
TASK_DESCRIPTION = range(10, 11)

# Multi-step command states
ADD_EMPLOYEE_USERNAME = range(11, 12)
ACCEPT_INVITATION_ID = range(12, 13)
REJECT_INVITATION_ID = range(13, 14)
TAKE_TASK_ID = range(14, 15)
ASSIGN_TASK_ID, ASSIGN_TASK_USERNAME = range(15, 17)
COMPLETE_TASK_ID = range(17, 18)
APPROVE_TASK_ID, APPROVE_TASK_QUALITY = range(18, 20)
REVISE_TASK_ID, REVISE_TASK_DEADLINE = range(20, 22)
REJECT_TASK_ID = range(22, 23)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
        
    except Exception as e:
        logger.error(f"Error in start command for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /balance command"""
    user_id = update.effective_user.id
    
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


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle regular text messages"""
    user_id = update.effective_user.id
    user_message = update.message.text
    
    # Check if it's a text message
    if not user_message:
        await update.message.reply_text(MESSAGES['invalid_message'], parse_mode='Markdown')
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
        success, error_msg = user_manager.process_request(user_id)
        
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
    """Start the finance conversation"""
    user_id = update.effective_user.id
    
    try:
        # Ensure user exists in database
        user_manager.get_or_create_user(
            user_id=user_id,
            username=update.effective_user.username,
            first_name=update.effective_user.first_name,
            last_name=update.effective_user.last_name
        )
        
        # Check if user already has business info
        has_info = user_manager.has_business_info(user_id)
        
        if has_info:
            await update.message.reply_text(
                MESSAGES['finance_has_info'],
                parse_mode='Markdown'
            )
            return CHECKING_EXISTING
        else:
            # Start the questionnaire
            await update.message.reply_text(
                MESSAGES['finance_welcome'],
                parse_mode='Markdown'
            )
            await update.message.reply_text(
                MESSAGES['finance_question_1'],
                parse_mode='Markdown'
            )
            return QUESTION_1
            
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
        success, error_msg = user_manager.process_request(user_id, tokens_amount=3)
        
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
            
            # Log usage and return
            user_manager.log_usage(
                user_id, 
                f"Finance plan request: {business_info.get('business_type', '')[:100]}", 
                financial_plan[:500],
                tokens_used=3
            )
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
        user_manager.log_usage(
            user_id, 
            f"Finance plan PDF request: {business_info.get('business_type', '')[:100]}", 
            f"PDF generated: {pdf_path}",
            tokens_used=3
        )
        
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
        success, error_msg = user_manager.process_request(user_id, tokens_amount=2)
        
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
        success, error_msg = user_manager.process_request(user_id, tokens_amount=2)
        
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
        businesses = user_manager.get_user_businesses(user_id)
        
        if not businesses:
            await update.message.reply_text(
                MESSAGES['my_businesses_empty'],
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
            MESSAGES['my_businesses_list'].format(businesses=businesses_text),
            parse_mode='Markdown'
        )
        
        logger.info(f"User {user_id} viewed their businesses")
        
    except Exception as e:
        logger.error(f"Error in my_businesses command for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])


# Task management command handlers
async def create_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the /create_task command"""
    user_id = update.effective_user.id
    
    try:
        # Check if user is business owner
        if not user_manager.is_business_owner(user_id):
            await update.message.reply_text(
                MESSAGES['task_no_business'],
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
    
    # Parse title, description, difficulty, priority, deadline
    parts = text.split('---')
    
    if len(parts) != 5:
        await update.message.reply_text(
            MESSAGES['task_invalid_format'],
            parse_mode='Markdown'
        )
        return TASK_DESCRIPTION
    
    title = parts[0].strip()
    description = parts[1].strip()
    difficulty_str = parts[2].strip()
    priority_str = parts[3].strip().lower()
    deadline_str = parts[4].strip()
    
    if not title or not description:
        await update.message.reply_text(
            MESSAGES['task_invalid_format'],
            parse_mode='Markdown'
        )
        return TASK_DESCRIPTION
    
    # Validate difficulty (1-5)
    try:
        difficulty = int(difficulty_str)
        if difficulty < 1 or difficulty > 5:
            await update.message.reply_text(
                MESSAGES['task_invalid_difficulty'],
                parse_mode='Markdown'
            )
            return TASK_DESCRIPTION
    except ValueError:
        await update.message.reply_text(
            MESSAGES['task_invalid_difficulty'],
            parse_mode='Markdown'
        )
        return TASK_DESCRIPTION
    
    # Validate priority
    valid_priorities = {
        'низкий': 'low',
        'средний': 'medium', 
        'высокий': 'high',
        'low': 'low',
        'medium': 'medium',
        'high': 'high'
    }
    
    priority = valid_priorities.get(priority_str)
    if not priority:
        await update.message.reply_text(
            MESSAGES['task_invalid_priority'],
            parse_mode='Markdown'
        )
        return TASK_DESCRIPTION
    
    # Validate deadline
    try:
        deadline_minutes = int(deadline_str)
        if deadline_minutes < 0:
            await update.message.reply_text(
                MESSAGES['task_invalid_deadline'],
                parse_mode='Markdown'
            )
            return TASK_DESCRIPTION
        # 0 means no deadline
        deadline_minutes = deadline_minutes if deadline_minutes > 0 else None
    except ValueError:
        await update.message.reply_text(
            MESSAGES['task_invalid_deadline'],
            parse_mode='Markdown'
        )
        return TASK_DESCRIPTION
    
    # Show thinking message
    thinking_msg = await update.message.reply_text("🤔 Создаю задачу и анализирую сотрудников...")
    
    try:
        # Create task with AI recommendation
        success, message, result = user_manager.create_task_with_ai_recommendation(
            user_id, title, description, difficulty, priority, deadline_minutes
        )
        
        if not success:
            await thinking_msg.edit_text(f"❌ {message}")
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
        logger.info(f"Task {task['id']} created by user {user_id}")
        
    except Exception as e:
        logger.error(f"Error creating task for user {user_id}: {e}")
        await thinking_msg.edit_text(MESSAGES['database_error'])
    
    return ConversationHandler.END


async def task_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel task creation"""
    await update.message.reply_text("❌ Создание задачи отменено")
    return ConversationHandler.END


async def available_tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /available_tasks command"""
    user_id = update.effective_user.id
    
    try:
        # Check for overdue tasks (manual check if no JobQueue)
        from database import business_repo
        business_repo.check_and_fail_overdue_tasks()
        
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
            
            # Add difficulty, priority, deadline
            if task.get('difficulty'):
                tasks_text += f"⭐ Сложность: {task['difficulty']}/5\n"
            if task.get('priority'):
                priority_names = {'low': '🟢 Низкий', 'medium': '🟡 Средний', 'high': '🔴 Высокий'}
                tasks_text += f"Приоритет: {priority_names.get(task['priority'], task['priority'])}\n"
            if task.get('deadline_minutes'):
                if task['deadline_minutes'] < 60:
                    tasks_text += f"⏱ Дедлайн: {task['deadline_minutes']} мин\n"
                elif task['deadline_minutes'] < 1440:
                    tasks_text += f"⏱ Дедлайн: {task['deadline_minutes']/60:.1f} ч\n"
                else:
                    tasks_text += f"⏱ Дедлайн: {task['deadline_minutes']/1440:.1f} дн\n"
            
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
        # Check for overdue tasks (manual check if no JobQueue)
        from database import business_repo
        business_repo.check_and_fail_overdue_tasks()
        
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
            status_names = {
                'assigned': '📌 Назначена',
                'in_progress': '🔄 В работе',
                'submitted': '📤 На проверке',
                'completed': '✅ Завершена'
            }
            status_display = status_names.get(task['status'], task['status'])
            
            tasks_text += f"*ID {task['id']}:* {escaped_title}\n"
            tasks_text += f"Бизнес: {escaped_business}\n"
            tasks_text += f"Статус: {status_display}\n"
            
            # Add difficulty, priority, deadline
            if task.get('difficulty'):
                tasks_text += f"⭐ Сложность: {task['difficulty']}/5\n"
            if task.get('priority'):
                priority_names = {'low': '🟢 Низкий', 'medium': '🟡 Средний', 'high': '🔴 Высокий'}
                tasks_text += f"Приоритет: {priority_names.get(task['priority'], task['priority'])}\n"
            if task.get('deadline_minutes') and task.get('assigned_at'):
                # Show time remaining
                from datetime import datetime
                time_passed = (datetime.now() - task['assigned_at']).total_seconds() / 60
                time_left = task['deadline_minutes'] - time_passed
                if time_left > 0:
                    if time_left < 60:
                        tasks_text += f"⏱ Осталось: {int(time_left)} мин\n"
                    elif time_left < 1440:
                        tasks_text += f"⏱ Осталось: {time_left/60:.1f} ч\n"
                    else:
                        tasks_text += f"⏱ Осталось: {time_left/1440:.1f} дн\n"
                else:
                    tasks_text += f"⏱ ⚠️ Просрочено на {int(abs(time_left))} мин\n"
            
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
            
            # Add difficulty, priority, deadline
            if task.get('difficulty'):
                tasks_text += f"⭐ Сложность: {task['difficulty']}/5\n"
            if task.get('priority'):
                priority_names = {'low': '🟢 Низкий', 'medium': '🟡 Средний', 'high': '🔴 Высокий'}
                tasks_text += f"Приоритет: {priority_names.get(task['priority'], task['priority'])}\n"
            if task.get('deadline_minutes'):
                if task['deadline_minutes'] < 60:
                    tasks_text += f"⏱ Дедлайн: {task['deadline_minutes']} мин\n"
                elif task['deadline_minutes'] < 1440:
                    tasks_text += f"⏱ Дедлайн: {task['deadline_minutes']/60:.1f} ч\n"
                else:
                    tasks_text += f"⏱ Дедлайн: {task['deadline_minutes']/1440:.1f} дн\n"
            
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
        # Check if user is business owner
        if not user_manager.is_business_owner(user_id):
            await update.message.reply_text(
                MESSAGES['task_no_business'],
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
            
            # Add difficulty, priority, deadline
            if task.get('difficulty'):
                tasks_text += f"⭐ Сложность: {task['difficulty']}/5\n"
            if task.get('priority'):
                priority_names = {'low': '🟢 Низкий', 'medium': '🟡 Средний', 'high': '🔴 Высокий'}
                tasks_text += f"Приоритет: {priority_names.get(task['priority'], task['priority'])}\n"
            if task.get('deadline_minutes') and task.get('assigned_at'):
                # Show time remaining
                from datetime import datetime
                time_passed = (datetime.now() - task['assigned_at']).total_seconds() / 60
                time_left = task['deadline_minutes'] - time_passed
                if time_left > 0:
                    if time_left < 60:
                        tasks_text += f"⏱ Осталось: {int(time_left)} мин\n"
                    elif time_left < 1440:
                        tasks_text += f"⏱ Осталось: {time_left/60:.1f} ч\n"
                    else:
                        tasks_text += f"⏱ Осталось: {time_left/1440:.1f} дн\n"
                else:
                    tasks_text += f"⏱ ⚠️ Просрочено на {int(abs(time_left))} мин\n"
            
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
    """Process submitting the task for review"""
    user_id = update.effective_user.id
    task_id = context.user_data.get('task_id')
    
    try:
        # Submit task for review
        success, message = user_manager.complete_task(user_id, task_id)
        
        if success:
            await update.message.reply_text(
                MESSAGES['task_submitted'],
                parse_mode='Markdown'
            )
            
            # Notify business owner
            from database import business_repo
            task = business_repo.get_task(task_id)
            if task:
                business = business_repo.get_business_by_id(task['business_id'])
                if business:
                    owner_id = business['owner_id']
                    employee_name = f"@{update.effective_user.username}" if update.effective_user.username else update.effective_user.first_name
                    escaped_task_title = escape_markdown(task['title'])
                    escaped_employee = escape_markdown(employee_name)
                    
                    try:
                        await context.bot.send_message(
                            chat_id=owner_id,
                            text=f"📤 *Задача сдана на проверку!*\n\n"
                                 f"Задача: {escaped_task_title}\n"
                                 f"ID: `{task_id}`\n"
                                 f"Сотрудник: {escaped_employee}\n\n"
                                 f"Проверить: `/review_tasks`",
                            parse_mode='Markdown'
                        )
                        logger.info(f"Notified owner {owner_id} about task {task_id} submission")
                    except Exception as e:
                        logger.warning(f"Failed to notify owner {owner_id}: {e}")
        else:
            await update.message.reply_text(f"❌ {message}", parse_mode='Markdown')
        
        logger.info(f"User {user_id} tried to submit task {task_id}: {success}")
        
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


async def review_tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /review_tasks command - view tasks submitted for review"""
    user_id = update.effective_user.id
    
    try:
        # Check for overdue tasks (manual check if no JobQueue)
        from database import business_repo
        business_repo.check_and_fail_overdue_tasks()
        
        # Check if user is business owner
        if not user_manager.is_business_owner(user_id):
            await update.message.reply_text(
                MESSAGES['task_no_business'],
                parse_mode='Markdown'
            )
            return
        
        # Get business
        business = user_manager.get_business(user_id)
        
        # Get submitted tasks
        tasks = business_repo.get_submitted_tasks(business['id'])
        
        if not tasks:
            await update.message.reply_text(
                MESSAGES['review_tasks_empty'],
                parse_mode='Markdown'
            )
            return
        
        # Format tasks list
        tasks_text = ""
        for task in tasks:
            employee = f"@{task['assigned_to_username']}" if task.get('assigned_to_username') else task.get('assigned_to_name', 'Unknown')
            escaped_title = escape_markdown(task['title'])
            escaped_employee = escape_markdown(employee)
            
            tasks_text += f"*ID {task['id']}:* {escaped_title}\n"
            tasks_text += f"Исполнитель: {escaped_employee}\n"
            
            if task.get('difficulty'):
                tasks_text += f"Сложность: {task['difficulty']}/5\n"
            if task.get('priority'):
                priority_names = {'low': 'Низкий', 'medium': 'Средний', 'high': 'Высокий'}
                tasks_text += f"Приоритет: {priority_names.get(task['priority'], task['priority'])}\n"
            
            # Calculate time taken
            if task.get('assigned_at') and task.get('submitted_at'):
                from datetime import datetime
                time_taken = (task['submitted_at'] - task['assigned_at']).total_seconds() / 60
                if time_taken < 60:
                    tasks_text += f"Время: {int(time_taken)} мин\n"
                elif time_taken < 1440:
                    tasks_text += f"Время: {time_taken/60:.1f} ч\n"
                else:
                    tasks_text += f"Время: {time_taken/1440:.1f} дн\n"
                
                # Show deadline status if exists
                if task.get('deadline_minutes'):
                    deadline_ratio = time_taken / task['deadline_minutes']
                    if deadline_ratio < 0.5:
                        tasks_text += "⚡ Выполнено очень быстро!\n"
                    elif deadline_ratio <= 1.0:
                        tasks_text += "✅ В срок\n"
                    else:
                        tasks_text += "⏰ С опозданием\n"
            
            tasks_text += "\n"
        
        await update.message.reply_text(
            MESSAGES['review_tasks'].format(tasks=tasks_text),
            parse_mode='Markdown'
        )
        logger.info(f"User {user_id} viewed submitted tasks")
        
    except Exception as e:
        logger.error(f"Error in review_tasks command for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])


# Approve task handlers
async def approve_task_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the approve task conversation"""
    user_id = update.effective_user.id
    
    try:
        # Check if user is business owner
        if not user_manager.is_business_owner(user_id):
            await update.message.reply_text(
                MESSAGES['task_no_business'],
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        # Ask for task ID
        await update.message.reply_text(
            "📋 Укажите ID задачи для принятия:",
            parse_mode='Markdown'
        )
        return APPROVE_TASK_ID
        
    except Exception as e:
        logger.error(f"Error in approve_task_start for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])
        return ConversationHandler.END


async def approve_task_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle task ID input for approve"""
    try:
        task_id = int(update.message.text.strip())
        context.user_data['task_id'] = task_id
        
        # Ask for quality coefficient
        await update.message.reply_text(
            "⭐ Укажите коэффициент качества выполнения (от 0.5 до 1.0):\n\n"
            "Примеры:\n"
            "• 1.0 - отлично выполнено\n"
            "• 0.8 - хорошо\n"
            "• 0.6 - удовлетворительно\n"
            "• 0.5 - минимальный уровень",
            parse_mode='Markdown'
        )
        return APPROVE_TASK_QUALITY
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат ID. Пожалуйста, введите число.",
            parse_mode='Markdown'
        )
        return APPROVE_TASK_ID


async def approve_task_quality_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle quality coefficient input"""
    try:
        quality = float(update.message.text.strip())
        if quality < 0.5 or quality > 1.0:
            await update.message.reply_text(
                MESSAGES['task_invalid_quality'],
                parse_mode='Markdown'
            )
            return APPROVE_TASK_QUALITY
        
        context.user_data['quality'] = quality
        return await approve_task_process(update, context)
    except ValueError:
        await update.message.reply_text(
            MESSAGES['task_invalid_quality'],
            parse_mode='Markdown'
        )
        return APPROVE_TASK_QUALITY


async def approve_task_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process task approval"""
    user_id = update.effective_user.id
    task_id = context.user_data.get('task_id')
    quality = context.user_data.get('quality')
    
    try:
        from database import business_repo
        
        # Approve task
        result = business_repo.approve_task(task_id, quality)
        
        if result:
            # Get employee username and notify
            task = business_repo.get_task(task_id)
            username = task.get('assigned_to_username', 'unknown')
            employee_id = task.get('assigned_to')
            escaped_username = escape_markdown(f"@{username}" if username != 'unknown' else username)
            
            # Notify owner
            await update.message.reply_text(
                MESSAGES['task_approved'].format(
                    username=escaped_username,
                    rating_change=result['rating_change'],
                    new_rating=result.get('new_rating', '?')
                ),
                parse_mode='Markdown'
            )
            
            # Notify employee
            if employee_id:
                try:
                    escaped_task_title = escape_markdown(task['title'])
                    await context.bot.send_message(
                        chat_id=employee_id,
                        text=f"✅ *Задача принята!*\n\n"
                             f"Задача: {escaped_task_title}\n"
                             f"ID: `{task_id}`\n\n"
                             f"Ваш рейтинг: *{result.get('new_rating', '?')}* "
                             f"(*+{result['rating_change']}*)\n\n"
                             f"🎉 Отличная работа!",
                        parse_mode='Markdown'
                    )
                    logger.info(f"Notified employee {employee_id} about task {task_id} approval")
                except Exception as e:
                    logger.warning(f"Failed to notify employee {employee_id}: {e}")
        else:
            await update.message.reply_text(
                "❌ Не удалось принять задачу. Проверьте ID и статус задачи.",
                parse_mode='Markdown'
            )
        
        logger.info(f"User {user_id} approved task {task_id} with quality {quality}")
        
    except Exception as e:
        logger.error(f"Error in approve_task_process for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])
    
    finally:
        context.user_data.clear()
    
    return ConversationHandler.END


async def approve_task_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel approve task conversation"""
    await update.message.reply_text("❌ Принятие задачи отменено")
    context.user_data.clear()
    return ConversationHandler.END


# Revise task handlers
async def revise_task_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the revise task conversation"""
    user_id = update.effective_user.id
    
    try:
        # Check if user is business owner
        if not user_manager.is_business_owner(user_id):
            await update.message.reply_text(
                MESSAGES['task_no_business'],
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        # Ask for task ID
        await update.message.reply_text(
            "📋 Укажите ID задачи для отправки на доработку:",
            parse_mode='Markdown'
        )
        return REVISE_TASK_ID
        
    except Exception as e:
        logger.error(f"Error in revise_task_start for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])
        return ConversationHandler.END


async def revise_task_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle task ID input for revise"""
    try:
        task_id = int(update.message.text.strip())
        context.user_data['task_id'] = task_id
        
        # Ask for new deadline
        await update.message.reply_text(
            "⏱ Укажите новый дедлайн в минутах:",
            parse_mode='Markdown'
        )
        return REVISE_TASK_DEADLINE
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат ID. Пожалуйста, введите число.",
            parse_mode='Markdown'
        )
        return REVISE_TASK_ID


async def revise_task_deadline_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle new deadline input"""
    try:
        deadline = int(update.message.text.strip())
        if deadline <= 0:
            await update.message.reply_text(
                MESSAGES['task_invalid_deadline'],
                parse_mode='Markdown'
            )
            return REVISE_TASK_DEADLINE
        
        context.user_data['deadline'] = deadline
        return await revise_task_process(update, context)
    except ValueError:
        await update.message.reply_text(
            MESSAGES['task_invalid_deadline'],
            parse_mode='Markdown'
        )
        return REVISE_TASK_DEADLINE


async def revise_task_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process task revision"""
    user_id = update.effective_user.id
    task_id = context.user_data.get('task_id')
    deadline = context.user_data.get('deadline')
    
    try:
        from database import business_repo
        
        # Get task info before revising (to notify employee)
        task = business_repo.get_task(task_id)
        employee_id = task.get('assigned_to') if task else None
        
        # Revise task
        success = business_repo.revise_task(task_id, deadline)
        
        if success:
            await update.message.reply_text(
                MESSAGES['task_revised'].format(deadline=deadline),
                parse_mode='Markdown'
            )
            
            # Notify employee
            if employee_id and task:
                try:
                    escaped_task_title = escape_markdown(task['title'])
                    if deadline < 60:
                        deadline_str = f"{deadline} минут"
                    elif deadline < 1440:
                        deadline_str = f"{deadline/60:.1f} часов"
                    else:
                        deadline_str = f"{deadline/1440:.1f} дней"
                    
                    await context.bot.send_message(
                        chat_id=employee_id,
                        text=f"🔄 *Задача отправлена на доработку*\n\n"
                             f"Задача: {escaped_task_title}\n"
                             f"ID: `{task_id}`\n\n"
                             f"Новый дедлайн: *{deadline_str}*\n\n"
                             f"Пожалуйста, доработайте задачу и сдайте повторно.",
                        parse_mode='Markdown'
                    )
                    logger.info(f"Notified employee {employee_id} about task {task_id} revision")
                except Exception as e:
                    logger.warning(f"Failed to notify employee {employee_id}: {e}")
        else:
            await update.message.reply_text(
                "❌ Не удалось отправить на доработку. Проверьте ID и статус задачи.",
                parse_mode='Markdown'
            )
        
        logger.info(f"User {user_id} revised task {task_id} with new deadline {deadline}")
        
    except Exception as e:
        logger.error(f"Error in revise_task_process for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])
    
    finally:
        context.user_data.clear()
    
    return ConversationHandler.END


async def revise_task_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel revise task conversation"""
    await update.message.reply_text("❌ Отправка на доработку отменена")
    context.user_data.clear()
    return ConversationHandler.END


# Reject task handlers
async def reject_task_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the reject task conversation"""
    user_id = update.effective_user.id
    
    try:
        # Check if user is business owner
        if not user_manager.is_business_owner(user_id):
            await update.message.reply_text(
                MESSAGES['task_no_business'],
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        # Ask for task ID
        await update.message.reply_text(
            "📋 Укажите ID задачи для отклонения:",
            parse_mode='Markdown'
        )
        return REJECT_TASK_ID
        
    except Exception as e:
        logger.error(f"Error in reject_task_start for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])
        return ConversationHandler.END


async def reject_task_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle task ID input for reject"""
    try:
        task_id = int(update.message.text.strip())
        context.user_data['task_id'] = task_id
        return await reject_task_process(update, context)
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат ID. Пожалуйста, введите число.",
            parse_mode='Markdown'
        )
        return REJECT_TASK_ID


async def reject_task_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process task rejection"""
    user_id = update.effective_user.id
    task_id = context.user_data.get('task_id')
    
    try:
        from database import business_repo
        
        # Get task info BEFORE rejecting (to get username)
        task = business_repo.get_task(task_id)
        username = task.get('assigned_to_username', 'unknown') if task else 'unknown'
        
        # Reject task
        result = business_repo.reject_task(task_id)
        
        if result:
            escaped_username = escape_markdown(f"@{username}" if username and username != 'unknown' else 'Неизвестный')
            new_rating = result.get('new_rating', 'неизвестен')
            employee_id = result.get('employee_id')
            
            # Notify owner
            await update.message.reply_text(
                MESSAGES['task_rejected'].format(
                    username=escaped_username,
                    new_rating=new_rating if new_rating != 'неизвестен' else '?'
                ),
                parse_mode='Markdown'
            )
            
            # Notify employee
            if employee_id and task:
                try:
                    escaped_task_title = escape_markdown(task['title'])
                    await context.bot.send_message(
                        chat_id=employee_id,
                        text=f"❌ *Задача отклонена*\n\n"
                             f"Задача: {escaped_task_title}\n"
                             f"ID: `{task_id}`\n\n"
                             f"Ваш рейтинг: *{new_rating if new_rating != 'неизвестен' else '?'}* "
                             f"(*-20*)\n\n"
                             f"Задача возвращена в пул доступных задач.",
                        parse_mode='Markdown'
                    )
                    logger.info(f"Notified employee {employee_id} about task {task_id} rejection")
                except Exception as e:
                    logger.warning(f"Failed to notify employee {employee_id}: {e}")
        else:
            await update.message.reply_text(
                "❌ Не удалось отклонить задачу. Проверьте ID и статус задачи.",
                parse_mode='Markdown'
            )
        
        logger.info(f"User {user_id} rejected task {task_id}")
        
    except Exception as e:
        logger.error(f"Error in reject_task_process for user {user_id}: {e}")
        await update.message.reply_text(MESSAGES['database_error'])
    
    finally:
        context.user_data.clear()
    
    return ConversationHandler.END


async def reject_task_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel reject task conversation"""
    await update.message.reply_text("❌ Отклонение задачи отменено")
    context.user_data.clear()
    return ConversationHandler.END


async def all_tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /all_tasks command"""
    user_id = update.effective_user.id
    
    try:
        # Check for overdue tasks (manual check if no JobQueue)
        from database import business_repo
        business_repo.check_and_fail_overdue_tasks()
        
        # Check if user is business owner
        if not user_manager.is_business_owner(user_id):
            await update.message.reply_text(
                MESSAGES['task_no_business'],
                parse_mode='Markdown'
            )
            return
        
        # Get all business tasks
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
        
        tasks_text = ""
        
        if available:
            tasks_text += "*📋 Доступные задачи:*\n"
            for task in available:
                escaped_title = escape_markdown(task['title'])
                tasks_text += f"  • ID {task['id']}: {escaped_title}"
                
                # Add difficulty and priority inline
                if task.get('difficulty'):
                    tasks_text += f" ⭐{task['difficulty']}"
                if task.get('priority'):
                    priority_emoji = {'low': '🟢', 'medium': '🟡', 'high': '🔴'}
                    tasks_text += f" {priority_emoji.get(task['priority'], '')}"
                if task.get('deadline_minutes'):
                    if task['deadline_minutes'] < 60:
                        tasks_text += f" ⏱{task['deadline_minutes']}мин"
                    elif task['deadline_minutes'] < 1440:
                        tasks_text += f" ⏱{task['deadline_minutes']/60:.0f}ч"
                    else:
                        tasks_text += f" ⏱{task['deadline_minutes']/1440:.0f}д"
                
                tasks_text += "\n"
            tasks_text += "\n"
        
        if assigned:
            tasks_text += "*👤 Назначенные/В работе:*\n"
            for task in assigned:
                assignee = f"@{task['assigned_to_username']}" if task.get('assigned_to_username') else task.get('assigned_to_name', 'Unknown')
                escaped_title = escape_markdown(task['title'])
                escaped_assignee = escape_markdown(assignee)
                tasks_text += f"  • ID {task['id']}: {escaped_title} → {escaped_assignee}"
                
                # Add difficulty and priority inline
                if task.get('difficulty'):
                    tasks_text += f" ⭐{task['difficulty']}"
                if task.get('priority'):
                    priority_emoji = {'low': '🟢', 'medium': '🟡', 'high': '🔴'}
                    tasks_text += f" {priority_emoji.get(task['priority'], '')}"
                
                # Show deadline status
                if task.get('deadline_minutes') and task.get('assigned_at'):
                    from datetime import datetime
                    time_passed = (datetime.now() - task['assigned_at']).total_seconds() / 60
                    time_left = task['deadline_minutes'] - time_passed
                    if time_left < 0:
                        tasks_text += f" ⚠️"
                    elif time_left < task['deadline_minutes'] * 0.2:
                        tasks_text += f" ⏰"
                
                tasks_text += "\n"
            tasks_text += "\n"
        
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


# Find similar users command handler
async def find_similar_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /find_similar command to find similar users for collaboration"""
    user_id = update.effective_user.id
    user = update.effective_user
    
    try:
        # Ensure user exists in database
        user_manager.get_or_create_user(
            user_id=user_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
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
            success, error_msg = user_manager.process_request(user_id, tokens_amount=2)
            
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
        BotCommand("employees", "Список сотрудников"),
        BotCommand("invitations", "Посмотреть приглашения"),
        BotCommand("accept", "Принять приглашение"),
        BotCommand("reject", "Отклонить приглашение"),
        BotCommand("my_businesses", "Мои работодатели"),
        BotCommand("create_task", "Создать задачу"),
        BotCommand("available_tasks", "Доступные задачи"),
        BotCommand("my_tasks", "Мои задачи"),
        BotCommand("all_tasks", "Все задачи бизнеса"),
        BotCommand("take_task", "Взять задачу"),
        BotCommand("assign_task", "Назначить задачу"),
        BotCommand("complete_task", "Завершить задачу"),
        BotCommand("abandon_task", "Отказаться от задачи"),
    ]
    
    await application.bot.set_my_commands(commands)
    logger.info("Bot commands registered successfully")
async def check_overdue_tasks_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Background job to check and fail overdue tasks"""
    try:
        from database import business_repo
        failed_tasks = business_repo.check_and_fail_overdue_tasks()
        
        if failed_tasks:
            logger.info(f"Background job: Failed {len(failed_tasks)} overdue tasks, sending notifications")
            
            # Send notifications for each failed task
            for task_info in failed_tasks:
                task_id = task_info['task_id']
                title = task_info['title']
                employee_id = task_info['employee_id']
                owner_id = task_info['owner_id']
                employee_username = task_info['employee_username']
                new_rating = task_info['new_rating']
                
                escaped_title = escape_markdown(title)
                
                # Notify employee
                if employee_id:
                    try:
                        await context.bot.send_message(
                            chat_id=employee_id,
                            text=f"⏰ *Задача просрочена!*\n\n"
                                 f"Задача: {escaped_title}\n"
                                 f"ID: `{task_id}`\n\n"
                                 f"Превышен дедлайн в 2 раза.\n"
                                 f"Ваш рейтинг: *{new_rating if new_rating else '?'}* (*-40*)\n\n"
                                 f"Задача возвращена в пул доступных задач.",
                            parse_mode='Markdown'
                        )
                        logger.info(f"Notified employee {employee_id} about overdue task {task_id}")
                    except Exception as e:
                        logger.warning(f"Failed to notify employee {employee_id}: {e}")
                
                # Notify owner
                if owner_id:
                    try:
                        employee_name = f"@{employee_username}" if employee_username else task_info.get('employee_name', 'Сотрудник')
                        escaped_employee = escape_markdown(employee_name)
                        
                        await context.bot.send_message(
                            chat_id=owner_id,
                            text=f"⏰ *Задача просрочена сотрудником*\n\n"
                                 f"Задача: {escaped_title}\n"
                                 f"ID: `{task_id}`\n"
                                 f"Сотрудник: {escaped_employee}\n\n"
                                 f"Превышен дедлайн в 2 раза.\n"
                                 f"Рейтинг сотрудника: *-40*\n\n"
                                 f"Задача возвращена в пул доступных задач.",
                            parse_mode='Markdown'
                        )
                        logger.info(f"Notified owner {owner_id} about overdue task {task_id}")
                    except Exception as e:
                        logger.warning(f"Failed to notify owner {owner_id}: {e}")
                        
    except Exception as e:
        logger.error(f"Error in overdue tasks check job: {e}")


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
        
        # Create the Application with custom request handler
        application = (
            Application.builder()
            .token(Config.TELEGRAM_BOT_TOKEN)
            .request(request)
            .build()
        )
        
        # Schedule background job to check overdue tasks every 5 minutes (if available)
        try:
            job_queue = application.job_queue
            if job_queue:
                job_queue.run_repeating(
                    check_overdue_tasks_job,
                    interval=300,  # 5 minutes
                    first=10  # Start after 10 seconds
                )
                logger.info("Scheduled overdue tasks check job (every 5 minutes)")
            else:
                logger.warning("JobQueue not available. Install with: pip install python-telegram-bot[job-queue]")
                logger.info("Overdue tasks will be checked manually on certain commands")
        except Exception as e:
            logger.warning(f"Could not setup JobQueue: {e}")
            logger.info("Overdue tasks will be checked manually on certain commands")
        
        # Register command handlers
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("balance", balance_command))
        application.add_handler(CommandHandler("roulette", roulette_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("find_similar", find_similar_command))
        
        # Register callback query handler for inline buttons
        application.add_handler(CallbackQueryHandler(invitation_callback_handler))
        
        # Register employee management command handlers
        application.add_handler(CommandHandler("employees", employees_command))
        application.add_handler(CommandHandler("invitations", invitations_command))
        application.add_handler(CommandHandler("my_businesses", my_businesses_command))
        
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
        application.add_handler(CommandHandler("review_tasks", review_tasks_command))
        
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
        
        # Register task review conversation handlers
        approve_task_handler = ConversationHandler(
            entry_points=[CommandHandler("approve_task", approve_task_start)],
            states={
                APPROVE_TASK_ID: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, approve_task_id_handler)
                ],
                APPROVE_TASK_QUALITY: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, approve_task_quality_handler)
                ],
            },
            fallbacks=[CommandHandler("cancel", approve_task_cancel)],
        )
        application.add_handler(approve_task_handler)
        
        revise_task_handler = ConversationHandler(
            entry_points=[CommandHandler("revise_task", revise_task_start)],
            states={
                REVISE_TASK_ID: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, revise_task_id_handler)
                ],
                REVISE_TASK_DEADLINE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, revise_task_deadline_handler)
                ],
            },
            fallbacks=[CommandHandler("cancel", revise_task_cancel)],
        )
        application.add_handler(revise_task_handler)
        
        reject_task_handler = ConversationHandler(
            entry_points=[CommandHandler("reject_task", reject_task_start)],
            states={
                REJECT_TASK_ID: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, reject_task_id_handler)
                ],
            },
            fallbacks=[CommandHandler("cancel", reject_task_cancel)],
        )
        application.add_handler(reject_task_handler)
        
        # Register create task conversation handler
        create_task_handler = ConversationHandler(
            entry_points=[CommandHandler("create_task", create_task_command)],
            states={
                TASK_DESCRIPTION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, task_description_handler)
                ],
            },
            fallbacks=[CommandHandler("cancel", task_cancel)],
        )
        application.add_handler(create_task_handler)
        
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
        
        # Register message handler
        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
        )
        
        # Register error handler
        application.add_error_handler(error_handler)
        
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
