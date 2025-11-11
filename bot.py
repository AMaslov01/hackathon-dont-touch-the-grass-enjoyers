"""
Telegram bot that integrates with Google Gemini 2.5 Flash
Handles /start and /prompt commands
"""

import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv('config.env')

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Validate environment variables
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash-exp')


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command"""
    welcome_message = (
        "👋 Welcome to the Gemini Bot!\n\n"
        "I can help you with anything using Google's Gemini 2.5 Flash AI.\n\n"
        "📝 How to use:\n"
        "/prompt <your question> - Ask me anything!\n\n"
        "Example:\n"
        "/prompt What is the capital of France?"
    )
    await update.message.reply_text(welcome_message)
    logger.info(f"User {update.effective_user.id} started the bot")


async def prompt_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /prompt command and send to Gemini"""
    # Extract the prompt from the command
    if not context.args:
        await update.message.reply_text(
            "⚠️ Please provide a prompt after the /prompt command.\n\n"
            "Example: /prompt Tell me a joke"
        )
        return
    
    user_prompt = ' '.join(context.args)
    user_id = update.effective_user.id
    
    logger.info(f"User {user_id} sent prompt: {user_prompt}")
    
    # Send "thinking" message
    thinking_message = await update.message.reply_text("🤔 Thinking...")
    
    try:
        # Generate response from Gemini
        response = model.generate_content(user_prompt)
        
        # Extract the text from response
        if response.text:
            response_text = response.text
            
            # Telegram message limit is 4096 characters
            if len(response_text) > 4000:
                response_text = response_text[:4000] + "\n\n... (response truncated)"
            
            # Edit the thinking message with the actual response
            await thinking_message.edit_text(f"💡 {response_text}")
            logger.info(f"Successfully responded to user {user_id}")
        else:
            await thinking_message.edit_text(
                "⚠️ I couldn't generate a response. Please try again."
            )
            logger.warning(f"Empty response from Gemini for user {user_id}")
            
    except Exception as e:
        error_message = f"❌ An error occurred: {str(e)}"
        await thinking_message.edit_text(error_message)
        logger.error(f"Error processing request for user {user_id}: {e}", exc_info=True)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")


def main() -> None:
    """Start the bot"""
    # Create the Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Register command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("prompt", prompt_command))
    
    # Register error handler
    application.add_error_handler(error_handler)
    
    # Start the bot
    logger.info("Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()

