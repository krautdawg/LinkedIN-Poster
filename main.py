import asyncio
import datetime
import json
import logging
import os
import sys
from typing import Dict, List

import openai
import requests
from linkedin_api.clients.restli.client import RestliClient
from newsapi.newsapi_client import NewsApiClient
from telegram.ext import Application, MessageHandler, filters

# Configure logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

# Environment variables
class Config:
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    NEWS_API_KEY = os.environ.get('NEWS_API_KEY')
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
    LINKEDIN_ACCESS_TOKEN = os.environ.get('LINKEDIN_ACCESS_TOKEN')
    LINKEDIN_MEMBER_ID = os.environ.get('LINKEDIN_MEMBER_ID')

# Initialize APIs
openai.api_key = Config.OPENAI_API_KEY
newsapi = NewsApiClient(api_key=Config.NEWS_API_KEY)

def check_environment():
    """Verify all required environment variables are set"""
    if not all([Config.OPENAI_API_KEY, Config.NEWS_API_KEY, Config.TELEGRAM_BOT_TOKEN, Config.TELEGRAM_CHAT_ID]):
        sys.stderr.write("""
        Missing required keys. Please set:
        - OPENAI_API_KEY
        - NEWS_API_KEY
        - TELEGRAM_BOT_TOKEN
        - TELEGRAM_CHAT_ID
        in the Secrets Tool.
        """)
        exit(1)

class NewsCollector:
    SOURCES = [
        'faz.net', 'sueddeutsche.de', 'zeit.de', 'welt.de', 'handelsblatt.com',
        'heise.de', 'golem.de', 't3n.de', 'spiegel.de', 'focus.de',
        'tagesschau.de', 'stern.de', 'wiwo.de', 'manager-magazin.de'
    ]

    @staticmethod
    def get_recent_news() -> List[Dict]:
        """Collect recent AI-related news from German sources"""
        all_articles = []
        seven_days_ago = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime('%Y-%m-%d')

        for source in NewsCollector.SOURCES:
            if len(all_articles) >= 3:
                break

            articles = newsapi.get_everything(
                q='("Künstliche Intelligenz" OR "KI-" OR ChatGPT) and (KMU OR "Kleine Unternehmen" OR Mittelstand OR "Mittlere Unternehmen" OR "Kleinst-unternehmen") AND NOT "KI-Newsletter"',
                language='de',
                sort_by='relevancy',
                page_size=1,
                domains=source,
                from_param=seven_days_ago
            )

            if articles['articles'] and not any(
                a['url'].split('/')[2] == articles['articles'][0]['url'].split('/')[2] 
                for a in all_articles
            ):
                all_articles.append(articles['articles'][0])

        return all_articles[:3]

class ContentGenerator:
    @staticmethod
    def create_linkedin_posts(articles: List[Dict]) -> Dict:
        """Generate LinkedIn posts using OpenAI"""
        posts = []
        for article in articles:
            content = f"Article: {article['title']}\nURL: {article['url']}\nDescription: {article['description']}"
            post_content = ContentGenerator._generate_post_content(content)
            sentiment = ContentGenerator._analyze_sentiment(content)

            posts.append({
                "content": post_content,
                "sourceUrl": article['url'],
                "sentiment": sentiment
            })
        return {"posts": posts}

    @staticmethod
    def _generate_post_content(content: str) -> str:
        """Generate post content using GPT-4o"""
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a humble consultant for small and medium sized businesses figuring out how to use AI applications for his clients. Please write a smart sounding German post for LinkedIN using the informal Du about this article. Write in a straightforward, professional tone that is approachable, humble and authentic. Balance insights and value for the reader with a witty style that feels relatable and grounded.  When appropriate incorporate elements of tech-savvy language with a focus on practical applications, especially in Artificial Intelligence and digitization for small and medium sized businesses. Keep the message concise to maximum 100 words. use no or at most 1 KIude relevant hashtags."},
                {"role": "user", "content": content}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content

    @staticmethod
    def _analyze_sentiment(content: str) -> Dict:
        """Analyze content sentiment using GPT-4"""
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Analyze the sentiment of this article. Return only two numbers: rating (1-5, where 5 is most positive) and confidence (0-1)."},
                {"role": "user", "content": content}
            ],
            temperature=0.3
        )

        try:
            rating, confidence = map(float, response.choices[0].message.content.split())
            rating = max(1, min(5, rating))
            confidence = max(0, min(1, confidence))
        except:
            rating, confidence = 3, 0.5

        return {"rating": rating, "confidence": confidence}

class Storage:
    @staticmethod
    def store_posts(posts: Dict) -> None:
        """Store posts in JSON file"""
        with open('stored_posts.json', 'w', encoding='utf-8') as f:
            json.dump(posts, f, ensure_ascii=False, indent=2)

    @staticmethod
    def store_selected_post(post: Dict) -> None:
        """Store selected post in JSON file"""
        with open('selected_post.json', 'w', encoding='utf-8') as f:
            json.dump(post, f, ensure_ascii=False, indent=2)

class SocialMedia:
    stored_posts = None

    @staticmethod
    async def send_to_telegram(posts: Dict) -> None:
        """Send posts to Telegram channel"""
        SocialMedia.stored_posts = posts
        try:
            bot = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
            await bot.initialize()
            Storage.store_posts(posts)

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
                    chat_id=Config.TELEGRAM_CHAT_ID,
                    text=message,
                    parse_mode='Markdown'
                )
            await bot.shutdown()

        except Exception as e:
            print(f"Error sending to Telegram: {str(e)}")
            sys.exit(1)

    @staticmethod
    async def post_to_linkedin(post_content: str, source_url: str, title: str = "AI News Article") -> bool:
        """Post content to LinkedIn"""
        if not Config.LINKEDIN_ACCESS_TOKEN or not Config.LINKEDIN_MEMBER_ID:
            raise Exception("LinkedIn credentials not found in environment variables")
            
        # Get meta tags from source URL
        thumbnail_url = None
        try:
            response = requests.get(source_url)
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try to get OpenGraph image first, then Twitter image, then any other image meta tag
            thumbnail_url = (
                soup.find('meta', property='og:image')
                or soup.find('meta', property='twitter:image')
                or soup.find('meta', property='image')
            )
            if thumbnail_url:
                thumbnail_url = thumbnail_url.get('content')
        except Exception as e:
            print(f"Error fetching meta tags: {str(e)}")
            
        try:
            headers = {
                "Authorization": f"Bearer {Config.LINKEDIN_ACCESS_TOKEN}",
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0"
            }

            payload = {
                "author": f"urn:li:person:{Config.LINKEDIN_MEMBER_ID}",
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {
                            "text": post_content[:3000]
                        },
                        "shareMediaCategory": "ARTICLE",
                        "media": [
                            {
                                "status": "READY",
                                "description": {
                                    "text": "AI News Update"
                                },
                                "originalUrl": source_url,
                                "title": {
                                    "text": title
                                },
                                "thumbnails": [{"url": thumbnail_url}] if thumbnail_url else []
                            }
                        ]
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                }
            }

            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: requests.post(
                    "https://api.linkedin.com/v2/ugcPosts",
                    headers=headers,
                    json=payload
                )
            )

            if response.status_code == 201:
                print("Successfully posted to LinkedIn!")
                return True
            print(f"Failed to post to LinkedIn. Status Code: {response.status_code}")
            print(f"Response: {response.text}")
            return False

        except Exception as e:
            error_message = str(e)

            if hasattr(e, 'response'):
                try:
                    error_details = e.response.json() if e.response.text else {}
                    print(f"LinkedIn API Error [{error_code}]:")
                    print(f"Message: {error_message}")
                    print(f"Full API Response: {error_details}")
                    print(f"Raw Response: {e.response.text}")
                except Exception as parse_error:
                    print(f"LinkedIn API Error [{error_code}]: {error_message}")
                    print(f"Could not parse response: {str(parse_error)}")
            else:
                print(f"LinkedIn API Error: {error_message}")
            return False

async def handle_selection(update, context):
    """Handle user selection of posts"""
    if not SocialMedia.stored_posts:
        await update.message.reply_text("No articles available. Please wait for the next update.")
        return

    try:
        selection = int(update.message.text)
        if 1 <= selection <= 3:
            selected_post = SocialMedia.stored_posts['posts'][selection - 1]
            await update.message.reply_text(
                f"Selected Article {selection}:\n\n"
                f"{selected_post['content']}\n\n"
                f"Source: {selected_post['sourceUrl']}"
            )
            Storage.store_selected_post(selected_post)

            post_content = selected_post['content'].split('\n\n')[0]
            # Get title from the source URL
            articles = NewsCollector.get_recent_news()
            title = next((article['title'] for article in articles if article['url'] == selected_post['sourceUrl']), "AI News Article")
            success = await SocialMedia.post_to_linkedin(post_content, selected_post['sourceUrl'], title)
            status_message = "Successfully posted to LinkedIn!" if success else "Failed to post to LinkedIn. Please check the logs."
            print(status_message)
            await context.bot.send_message(
                chat_id=Config.TELEGRAM_CHAT_ID,
                text=status_message
            )
            print("Script will end in 1 minute...")
            await asyncio.sleep(60)  # Wait for 1 minute
            try:
                app = context.application
                await app.stop()
                await app.shutdown()
                await app.bot.close()
            except Exception as e:
                print(f"Shutdown error: {e}")
            finally:
                sys.exit(0)
        else:
            await update.message.reply_text("Please select a number between 1 and 3.")
    except (ValueError, IndexError):
        await update.message.reply_text("Please send a number between 1 and 3 to select an article.")

async def main():
    """Main application entry point"""
    try:
        articles = NewsCollector.get_recent_news()
        posts = ContentGenerator.create_linkedin_posts(articles)
        await SocialMedia.send_to_telegram(posts)
        print("Successfully sent posts to Telegram")
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

async def initialize():
    check_environment()
    application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_selection))
    
    try:
        await application.initialize()
        await application.start()
        await main()
        await application.run_polling(drop_pending_updates=True)
    except Exception as e:
        print(f"Error during execution: {e}")
        raise e

if __name__ == '__main__':
    asyncio.run(initialize())