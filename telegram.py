
import os
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncio
from main import get_recent_news, create_linkedin_posts

# Check for Telegram Bot Token
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

if not TELEGRAM_BOT_TOKEN:
    sys.stderr.write("""
    Missing Telegram Bot Token. Please set:
    - TELEGRAM_BOT_TOKEN
    in the Secrets Tool.
    """)
    exit(1)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Hello! Use /posts to get the latest AI news posts.')

async def get_posts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Fetching latest AI news posts...')
    
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
            await update.message.reply_text(message, parse_mode='Markdown')
            
    except Exception as e:
        await update.message.reply_text(f"Error fetching posts: {str(e)}")

async def main() -> None:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("posts", get_posts))

    await app.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
