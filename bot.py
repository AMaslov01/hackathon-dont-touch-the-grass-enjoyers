"""
Telegram bot with AI integration, user accounts, and token system
"""
import os
import logging
from telegram import Update
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    ConversationHandler,
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

# Finance conversation states
CHECKING_EXISTING, QUESTION_1, QUESTION_2, QUESTION_3 = range(4)

# Clients search conversation states
CLIENTS_CHECKING, CLIENTS_QUESTION = range(4, 6)

# Executors search conversation states
EXECUTORS_CHECKING, EXECUTORS_QUESTION = range(6, 8)


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


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /help command"""
    await update.message.reply_text(MESSAGES['help'], parse_mode='Markdown')
    logger.info(f"User {update.effective_user.id} requested help")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle regular text messages"""
    user_id = update.effective_user.id
    user_message = update.message.text
    
    # Check if it's a text message
    if not user_message:
        await update.message.reply_text(MESSAGES['invalid_message'], parse_mode='Markdown')
        return
    
    logger.info(f"User {user_id} sent message: {user_message[:50]}...")
    
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
    """Handle answer to question 1 and ask question 2"""
    user_id = update.effective_user.id
    
    # Save answer to context
    context.user_data['business_type'] = update.message.text
    
    # Ask question 2, contextualizing it with answer from question 1
    business_type = update.message.text
    custom_q2 = (
        f"💰 *Вопрос 2/3*\n\n"
        f"Отлично! Теперь расскажите о финансовой ситуации вашего бизнеса ({business_type[:50]}...):\n"
        f"- Каковы ваши основные источники дохода?\n"
        f"- Примерный месячный оборот?\n"
        f"- Основные статьи расходов?"
    )
    
    await update.message.reply_text(custom_q2, parse_mode='Markdown')
    logger.info(f"User {user_id} answered question 1")
    return QUESTION_2


async def finance_question_2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle answer to question 2 and ask question 3"""
    user_id = update.effective_user.id
    
    # Save answer to context
    context.user_data['financial_situation'] = update.message.text
    
    # Ask question 3, contextualizing it with previous answers
    financial_sit = update.message.text
    custom_q3 = (
        f"🎯 *Вопрос 3/3*\n\n"
        f"Понятно. Последний вопрос о ваших целях:\n"
        f"- Какие финансовые цели вы хотите достичь?\n"
        f"- В какой срок?\n"
        f"- Какие проблемы/вызовы вы видите на пути к этим целям?"
    )
    
    await update.message.reply_text(custom_q3, parse_mode='Markdown')
    logger.info(f"User {user_id} answered question 2")
    return QUESTION_3


async def finance_question_3(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle answer to question 3 and generate financial plan"""
    user_id = update.effective_user.id
    
    # Save answer to context
    context.user_data['goals'] = update.message.text
    
    logger.info(f"User {user_id} completed all questions")
    
    # Save business info to database
    try:
        success = user_manager.save_business_info(
            user_id=user_id,
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
                'business_type': context.user_data['business_type'],
                'financial_situation': context.user_data['financial_situation'],
                'goals': context.user_data['goals']
            }
        
        if not business_info:
            await thinking_msg.edit_text(MESSAGES['finance_no_info'])
            return ConversationHandler.END
        
        # Update status message
        await thinking_msg.edit_text("🤖 Генерирую финансовый план с помощью AI...(это может занять некоторое время)")
        
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
                    try:
                        await update.message.reply_text(header + chunk, parse_mode='Markdown')
                    except BadRequest:
                        await update.message.reply_text(header + chunk)
            else:
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
                    parsed_user = {
                        'user_id': user_data['user_id'],
                        'username': user_data.get('username'),
                        'business_info': json.loads(user_data['business_info']) if user_data.get('business_info') else {},
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
        
        # Register command handlers
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("balance", balance_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("find_similar", find_similar_command))
        
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
