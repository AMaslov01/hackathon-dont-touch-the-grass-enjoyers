# hackathon-dont-touch-the-grass-enjoyers

A Telegram bot integrated with Google Gemini 2.5 Flash AI for intelligent conversations.

## Features

- 🤖 Telegram bot interface
- 🧠 Powered by Google Gemini 2.5 Flash
- ⚡ Fast and responsive
- 📝 Simple prompt-based interaction

## Prerequisites

- Python 3.10 or higher (3.14 recommended)
- Telegram Bot Token (from @BotFather)
- Google Gemini API Key

## Setup Instructions

### 1. Create a Virtual Environment

```bash
python3.14 -m venv venv
```

### 2. Activate the Virtual Environment

**On macOS/Linux:**
```bash
source venv/bin/activate
```

**On Windows:**
```bash
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure API Keys

Create a `.env` file in the project root (copy from template):

```bash
cp config.env .env
```

Then edit `.env` and add your credentials:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
GEMINI_API_KEY=your_gemini_api_key_here
```

**How to get API keys:**

1. **Telegram Bot Token**:
   - Open Telegram and message [@BotFather](https://t.me/botfather)
   - Send `/newbot` and follow instructions
   - Copy the token provided

2. **Gemini API Key**:
   - Visit [Google AI Studio](https://aistudio.google.com/app/apikey)
   - Sign in with your Google account
   - Click "Create API Key"
   - Copy the key

## Running the Bot

Start the bot with:

```bash
python bot.py
```

You should see:
```
INFO - Bot is starting...
```

The bot is now running and waiting for messages!

## Using the Bot

1. Open Telegram and find your bot (search for the name you gave it)
2. Send `/start` to initialize the bot
3. Use `/prompt <your question>` to interact with Gemini

**Examples:**

```
/prompt What is Python?
/prompt Write a haiku about coding
/prompt Explain quantum computing in simple terms
```

## Project Structure

```
hackathon-dont-touch-the-grass-enjoyers/
├── bot.py                 # Main bot script
├── requirements.txt       # Python dependencies
├── config.env.example     # API keys template
├── .env                   # Your API keys (not in git)
├── README.md             # This file
└── venv/                 # Virtual environment
```

## Development Tools

This project uses:
- **ruff**: Fast Python linter and formatter
- **pyright**: Static type checker for Python

### Running Linter

```bash
ruff check .
```

### Running Type Checker

```bash
pyright
```

## Troubleshooting

### Bot doesn't respond
- Check that `.env` file exists with correct API keys
- Verify bot token is correct (test with @BotFather)
- Check internet connection

### "TELEGRAM_BOT_TOKEN not found" error
- Make sure `.env` file is in the project root
- Verify variable names match exactly

### Gemini API errors
- Verify API key is valid at [AI Studio](https://aistudio.google.com/)
- Check you have available quota (Gemini has free tier)
- Ensure API key has proper permissions

## Deactivating the Virtual Environment

When you're done working, deactivate the virtual environment:

```bash
deactivate
```

## Architecture

```
User → Telegram → Bot Script → Gemini API → Response → User
```

The bot runs on your local machine/server, receives messages via Telegram's API, sends prompts to Google's Gemini API, and returns responses to the user.