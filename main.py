import openai
import os
import sys
import asyncio
import json
import logging
import requests
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
from newsapi.newsapi_client import NewsApiClient
import datetime
from telegram.ext import Application, CommandHandler, MessageHandler, filters

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
            q=f'("Künstliche Intelligenz") AND NOT "ChatGPT" AND NOT "KI-Newsletter"',
            language='de',
            sort_by='relevancy',
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
                {"role": "system", "content": "You are a LinkedIn content expert specializing in AI trends. Create an engaging German post using the informal Du about this article. Include relevant hashtags."},
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

def store_posts(posts):
    with open('stored_posts.json', 'w', encoding='utf-8') as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)

async def send_to_telegram(posts):
    global stored_posts
    stored_posts = posts
    try:
        bot = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        await bot.initialize()
        store_posts(posts)  # Store posts for future processing

        for i, post in enumerate(posts['posts'], 1):
            message = f"""
📰 *AI News Update #{i}*

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

async def main():
    try:
        articles = get_recent_news()
        posts = create_linkedin_posts(articles)
        await send_to_telegram(posts)
        print("Successfully sent posts to Telegram")
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

stored_posts = None

async def post_to_linkedin(post_content):
    access_token = os.environ.get('LINKEDIN_ACCESS_TOKEN')
    linkedin_member_id = os.environ.get('LINKEDIN_MEMBER_ID')

    if not access_token:
        raise Exception("LinkedIn access token not found in environment variables")
    if not linkedin_member_id:
        raise Exception("LinkedIn member ID not found in environment variables")

    try:
        restli_client = RestliClient()
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: restli_client.create(
                resource_path="/posts",
                entity={
                    "author": f"urn:li:person:{linkedin_member_id}",
                    "commentary": post_content[:3000],
                    "visibility": "PUBLIC",
                    "distribution": {
                        "feedDistribution": "MAIN_FEED",
                        "targetEntities": [],
                        "thirdPartyDistributionChannels": [],
                    },
                    "lifecycleState": "PUBLISHED",
                },
                version_string="202302",
                access_token=access_token
            )
        )
        return True
    except Exception as e:
        print(f"Error posting to LinkedIn: {str(e)}")
        return False

async def handle_selection(update, context):
    global stored_posts
    if not stored_posts:
        await update.message.reply_text("No articles available. Please wait for the next update.")
        return

    try:
        selection = int(update.message.text)
        if 1 <= selection <= 3:
            selected_post = stored_posts['posts'][selection - 1]
            await update.message.reply_text(
                f"Selected Article {selection}:\n\n"
                f"{selected_post['content']}\n\n"
                f"Source: {selected_post['sourceUrl']}"
            )
            # Store selection for future processing
            with open('selected_post.json', 'w', encoding='utf-8') as f:
                json.dump(selected_post, f, ensure_ascii=False, indent=2)

            # Post to LinkedIn
            success = await post_to_linkedin(selected_post['content'])
            if success:
                await update.message.reply_text("Successfully posted to LinkedIn!")
            else:
                await update.message.reply_text("Failed to post to LinkedIn. Please check the logs.")
        else:
            await update.message.reply_text("Please select a number between 1 and 3.")
    except (ValueError, IndexError):
        await update.message.reply_text("Please send a number between 1 and 3 to select an article.")

if __name__ == '__main__':
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_selection))

    # Run the bot and the main function
    asyncio.get_event_loop().create_task(main())
    application.run_polling()