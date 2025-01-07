
import os
import sys
from telegram.ext import Application
import asyncio

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

async def test_bot():
    try:
        print("Testing Telegram bot configuration...")
        print(f"Chat ID being used: {TELEGRAM_CHAT_ID}")
        
        app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Try to send a test message
        await app.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text="🔔 Test message - If you see this, your Telegram bot is configured correctly!"
        )
        print("Test message sent successfully!")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Error: Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID in Secrets")
        sys.exit(1)
    asyncio.run(test_bot())
