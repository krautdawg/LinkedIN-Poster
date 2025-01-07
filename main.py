
import openai
import os
import sys
import asyncio
from newsapi.newsapi_client import NewsApiClient
import datetime
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from telegram import Update

# API key checks
openai.api_key = os.environ.get('OPENAI_API_KEY')
newsapi = NewsApiClient(api_key=os.environ.get('NEWS_API_KEY'))
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

if not all([openai.api_key, os.environ.get('NEWS_API_KEY'), TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
    sys.stderr.write("""
    Missing required keys. Please set:
    - OPENAI_API_KEY
    - NEWS_API_KEY
    - TELEGRAM_BOT_TOKEN
    - TELEGRAM_CHAT_ID
    in the Secrets Tool.
    """)
    exit(1)

def get_recent_news():
    sources = [
        'faz.net', 'sueddeutsche.de', 'zeit.de', 'welt.de', 'handelsblatt.com',
        'heise.de', 'golem.de', 't3n.de', 'spiegel.de', 'focus.de',
        'tagesschau.de', 'stern.de', 'wiwo.de', 'manager-magazin.de'
    ]
    
    all_articles = []
    seven_days_ago = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
    
    for source in sources:
        if len(all_articles) >= 3:
            break
            
        articles = newsapi.get_everything(
            q=f'("Künstliche Intelligenz") AND NOT "ChatGPT"',
            language='de',
            sort_by='publishedAt',
            page_size=1,
            domains=source,
            from_param=seven_days_ago
        )
        
        if articles['articles'] and not any(a['url'].split('/')[2] == articles['articles'][0]['url'].split('/')[2] for a in all_articles):
            all_articles.append(articles['articles'][0])
            
    return all_articles[:3]

def create_linkedin_posts(articles):
    posts = []
    for article in articles:
        content = f"Article: {article['title']}\nURL: {article['url']}\nDescription: {article['description']}"
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a LinkedIn content expert specializing in AI trends. Create an engaging German post about this article. Include relevant hashtags."},
                {"role": "user", "content": content}
            ],
            temperature=0.7
        )

        sentiment_response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Analyze the sentiment of this article. Return only two numbers: rating (1-5, where 5 is most positive) and confidence (0-1)."},
                {"role": "user", "content": content}
            ],
            temperature=0.3
        )

        sentiment_text = sentiment_response.choices[0].message.content
        try:
            rating, confidence = map(float, sentiment_text.split())
            rating = max(1, min(5, rating))
            confidence = max(0, min(1, confidence))
        except:
            rating, confidence = 3, 0.5

        posts.append({
            "content": response.choices[0].message.content,
            "sourceUrl": article['url'],
            "sentiment": {
                "rating": rating,
                "confidence": confidence
            }
        })
    return {"posts": posts}

async def send_to_telegram(posts):
    try:
        bot = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        await bot.initialize()
        
        for post in posts['posts']:
            message = f"""
📰 *AI News Update*

{post['content']}

📊 Sentiment Analysis:
Rating: {'⭐' * int(post['sentiment']['rating'])} ({post['sentiment']['rating']}/5)
Confidence: {post['sentiment']['confidence']*100:.1f}%

🔗 Source: {post['sourceUrl']}
"""
            await bot.bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=message,
                parse_mode='Markdown'
            )
        await bot.shutdown()
            
    except Exception as e:
        print(f"Error sending to Telegram: {str(e)}")
        sys.exit(1)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Hello! I am your AI News Bot. Use /news to get the latest AI news.')

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        articles = get_recent_news()
        posts = create_linkedin_posts(articles)
        await send_to_telegram(posts)
        await update.message.reply_text('News has been fetched and posted!')
    except Exception as e:
        await update.message.reply_text(f'Error fetching news: {str(e)}')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
Available commands:
/start - Start the bot
/help - Show this help message
/news - Get latest AI news
    """
    await update.message.reply_text(help_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_type = update.message.chat.type
    text = update.message.text
    
    if message_type == 'group':
        if '@AINewsBot' not in text:
            return
        
    await update.message.reply_text('Use /help to see available commands')

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f'Update {update} caused error {context.error}')

async def main():
    try:
        app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Commands
        app.add_handler(CommandHandler('start', start_command))
        app.add_handler(CommandHandler('help', help_command))
        app.add_handler(CommandHandler('news', news_command))
        
        # Messages
        app.add_handler(MessageHandler(filters.TEXT, handle_message))
        
        # Errors
        app.add_error_handler(error)
        
        # Start bot
        print('Starting bot...')
        await app.run_polling(poll_interval=3)
        
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())
