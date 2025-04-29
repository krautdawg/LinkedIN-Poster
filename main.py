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
    @staticmethod
    def get_recent_news() -> List[Dict]:
        """Collect recent AI-related news from German sources"""
        one_day_ago = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        
        query = (
            '("Künstliche Intelligenz" OR "KI" OR ChatGPT)'
            ' AND Agenten'
            ' NOT ("KI-Newsletter" OR "ETFs" OR "OMR")'
        )
        
        print(f"Fetching news with query: {query}")
        print(f"From date: {one_day_ago}")
        
        articles = newsapi.get_everything(
            q=query,
            language='de',
            sort_by='relevancy',
            page_size=20,  # Increased to have more articles to filter from
            from_param=one_day_ago
        )
        
        # Filter articles to have max 2 per domain
        from urllib.parse import urlparse
        domain_count = {}
        filtered_articles = []
        
        for article in articles['articles']:
            domain = urlparse(article['url']).netloc
            if domain not in domain_count:
                filtered_articles.append(article)
                domain_count[domain] = 1
                
            if len(filtered_articles) >= 5:
                break
                
        print(f"Total articles found after filtering: {len(filtered_articles)}")
        if filtered_articles:
            print("\nFirst article preview:")
            first = filtered_articles[0]
            print(f"Title: {first.get('title')}")
            print(f"Source: {first.get('url')}")
            print(f"Published: {first.get('publishedAt')}")
        else:
            print("No articles found!")
        
        return filtered_articles[:5]

class ContentGenerator:
    @staticmethod
    def create_linkedin_posts(articles: List[Dict]) -> Dict:
        """Generate LinkedIn posts using OpenAI"""
        posts = []
        for article in articles:
            content = f"Article: {article['title']}\nURL: {article['url']}\nDescription: {article['description']}"
            post_content = ContentGenerator._generate_post_content(content)
            posts.append({
                "content": post_content,
                "sourceUrl": article['url']
            })
        return {"posts": posts}

    @staticmethod
    def _generate_post_content(content: str) -> str:
        """Generate LinkedIn post content"""
        from db_manager import PostDatabase
        stored_posts = PostDatabase.get_all_posts()
        stored_posts_text = "\n\n".join([post.get('content', '') for post in stored_posts[-5:]])  # Last 5 posts
        
        response = openai.chat.completions.create(
            model="gpt-4.1-nano-2025-04-14",
            messages=[
    {"role": "system", "content": "You are a professional content strategist and copywriter specializing for an AI Agent Consultant in crafting engaging and authentic LinkedIn posts for small and medium-sized businesses (SMBs) interested in leveraging AI. Your primary task is to analyze the provided news article (you will receive its URL and description) and create a post that alludes to the specific insights from this article. The posts needs to sound unique compared to the previous 5 articles"},
    {"role": "user", "content": f"<Article Content>{content}</Article Content>\n\n<Context>The user has shared the url news article relevant to AI and SMBs and needs to reflect on it with practical tips about how SMBs can effectively use AI agents to streamline their daily operations. Transform this input into a polished, concise, and engaging LinkedIn post in informal German using the Du-Form, aimed at SMB decision-makers. Use a professional yet friendly tone, incorporating humor lightly to spark interest. Avoid emojis and keep the post under 120 words, using relevant hashtags. IMPORTANT: Your response MUST alluded to the content from the provided article URL.</Context><Instructions>- Start with an insight from the article- Clearly outline practical ways SMBs can integrate AI agents, highlighting concrete benefits for daily business operations.- Conclude with an engaging question or reflective statement to encourage interactions.- Keep paragraphs short (1-2 sentences each) for readability.- Use relevant hashtags strategically (e.g., #KI, #KMU, #Digitalisierung).</Instructions><Constraints>Avoid buzzwords without clear meaning | Overpromising or exaggerated claims | Clickbait phrases | Emojis or overly informal language</Constraints>"}
            ],
            temperature=0.9
        )
        return response.choices[0].message.content

    

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
            print("Starting Telegram bot...")
            bot = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).connection_pool_size(8).pool_timeout(30.0).connect_timeout(30.0).read_timeout(30.0).write_timeout(30.0).build()
            
            print("Initializing bot...")
            await bot.initialize()
            Storage.store_posts(posts)

            from db_manager import PostDatabase
            unique_posts = [post for post in posts['posts'] if not PostDatabase.is_duplicate_article(post['sourceUrl'])]
            print(f"Sending {len(unique_posts)} unique posts to Telegram...")
            
            for i, post in enumerate(unique_posts, 1):
                try:
                    message = f"""
📰 *AI News Update #{i}*

{post['content']}

🔗 Source: {post['sourceUrl']}
"""
                    print(f"Sending post {i}...")
                    await bot.bot.send_message(
                        chat_id=Config.TELEGRAM_CHAT_ID,
                        text=message,
                        parse_mode='Markdown',
                        disable_web_page_preview=True
                    )
                    print(f"Post {i} sent successfully")
                except Exception as post_error:
                    print(f"Error sending post {i}: {str(post_error)}")
                    continue
            
            print("All posts processed. Shutting down bot...")
            await bot.shutdown()

        except Exception as e:
            print(f"Critical error sending to Telegram: {str(e)}")
            if "chat not found" in str(e).lower():
                print(f"Please check if the TELEGRAM_CHAT_ID ({Config.TELEGRAM_CHAT_ID}) is correct")
            elif "unauthorized" in str(e).lower():
                print(f"Please check if the TELEGRAM_BOT_TOKEN is correct")
            else:
                print("Please check your Telegram configuration")
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
        if 1 <= selection <= 5:
            selected_post = SocialMedia.stored_posts['posts'][selection - 1]
            await update.message.reply_text(
                f"Selected Article {selection}:\n\n"
                f"{selected_post['content']}\n\n"
                f"Source: {selected_post['sourceUrl']}"
            )
            Storage.store_selected_post(selected_post)

            post_content = selected_post['content']
            # Get title from the source URL
            articles = NewsCollector.get_recent_news()
            title = next((article['title'] for article in articles if article['url'] == selected_post['sourceUrl']), "AI News Article")
            success = await SocialMedia.post_to_linkedin(post_content, selected_post['sourceUrl'], title)
            if success:
                from db_manager import PostDatabase
                PostDatabase.store_post({
                    "content": post_content,
                    "url": selected_post['sourceUrl'],
                    "title": title,
                    "platform": "linkedin"
                })
            status_message = "Successfully posted to LinkedIn!" if success else "Failed to post to LinkedIn. Please check the logs."
            print(status_message)
            await context.bot.send_message(
                chat_id=Config.TELEGRAM_CHAT_ID,
                text=status_message
            )
            print("Shutting down...")
            await application.stop()
            await application.shutdown()
            sys.exit(0)
        else:
            await update.message.reply_text("Please select a number between 1 and 5.")
    except (ValueError, IndexError):
        await update.message.reply_text("Please send a number between 1 and 3 to select an article.")

async def main():
    """Main application entry point"""
    try:
        articles = NewsCollector.get_recent_news()
        if not articles:
            print("No articles found. Shutting down...")
            sys.exit(0)
            
        posts = ContentGenerator.create_linkedin_posts(articles)
        await SocialMedia.send_to_telegram(posts)
        print("Successfully sent posts to Telegram")
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

async def start_bot():
    """Start the bot and keep it running"""
    try:
        await main()
        print("Bot is running and waiting for your selection...")
        await application.initialize()
        await application.start()
        # Set polling timeout to 12 hours (43200 seconds)
        await application.updater.start_polling(
            drop_pending_updates=True,
            timeout=43200.0,
            read_timeout=43200.0,
            write_timeout=30.0
        )
        while application.running:
            await asyncio.sleep(1)
    except Exception as e:
        print(f"Error in start_bot: {str(e)}")
        if application.updater and application.updater.running:
            await application.updater.stop()
        await application.stop()

if __name__ == '__main__':
    check_environment()
    application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_selection))
    try:
        print("Starting bot...")
        asyncio.run(start_bot())
        # Keep the script running
        while True:
            asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Error running bot: {str(e)}")