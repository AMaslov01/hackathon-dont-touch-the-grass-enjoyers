"""
Telegram bot with AI integration, user accounts, and token system
"""
import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import BadRequest

# Import our modules
from config import Config
from database import db
from ai_client import ai_client
from user_manager import user_manager
from constants import MESSAGES

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


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
        
        # Create the Application
        application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
        
        # Register command handlers
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("balance", balance_command))
        application.add_handler(CommandHandler("help", help_command))
        
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
