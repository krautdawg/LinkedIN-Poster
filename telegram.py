
import os
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncio
from main import get_recent_news, create_linkedin_posts

# Check for Telegram Bot Token and Chat ID
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    sys.stderr.write("""
    Missing environment variables. Please set:
    - TELEGRAM_BOT_TOKEN
    - TELEGRAM_CHAT_ID
    in the Secrets Tool.
    """)
    exit(1)

async def send_posts(app) -> None:
    try:
        articles = get_recent_news()
        posts = create_linkedin_posts(articles)
        
        for post in posts['posts']:
            message = f"""
📰 *AI News Update*

{post['content']}

📊 Sentiment Analysis:
Rating: {'⭐' * int(post['sentiment']['rating'])} ({post['sentiment']['rating']}/5)
Confidence: {post['sentiment']['confidence']*100:.1f}%

🔗 Source: {post['sourceUrl']}
"""
            await app.bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=message,
                parse_mode='Markdown'
            )
            
    except Exception as e:
        await app.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=f"Error fetching posts: {str(e)}"
        )

async def main() -> None:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Send posts immediately when bot starts
    await send_posts(app)
    
    # Exit after sending posts
    sys.exit(0)

if __name__ == '__main__':
    asyncio.run(main())
