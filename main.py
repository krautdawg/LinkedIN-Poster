import openai
import os
import sys
from flask import Flask, request, render_template_string
from newsapi.newsapi_client import NewsApiClient
import datetime

app = Flask(__name__)

# API key checks
openai.api_key = os.environ.get('OPENAI_API_KEY')
newsapi = NewsApiClient(api_key=os.environ.get('NEWS_API_KEY'))

if not openai.api_key or not os.environ.get('NEWS_API_KEY'):
    sys.stderr.write("""
    Missing API keys. Please set:
    - OPENAI_API_KEY
    - NEWS_API_KEY
    in the Secrets Tool.
    """)
    exit(1)



def get_recent_news():
    # Define diverse German news sources
    sources = [
        'faz.net', 'sueddeutsche.de', 'zeit.de', 'welt.de', 'handelsblatt.com',
        'heise.de', 'golem.de', 't3n.de', 'spiegel.de', 'focus.de',
        'tagesschau.de', 'stern.de', 'wiwo.de', 'manager-magazin.de'
    ]
    
    all_articles = []
    seven_days_ago = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
    
    # Diverse AI-related topics
    topics = [
        'KI Gesundheit', 'KI Wirtschaft', 'KI Bildung',
        'KI Forschung', 'KI Ethik', 'KI Robotik',
        'KI Automation', 'KI Gesellschaft', 'KI Zukunft'
    ]
    
    # Get articles from different sources with varied topics
    for source in sources:
        for topic in topics:
            if len(all_articles) >= 3:
                break
                
            articles = newsapi.get_everything(
                q=f'("{topic}" OR "Künstliche Intelligenz") AND NOT "ChatGPT"',
                language='de',
                sort_by='publishedAt',
                page_size=1,
                domains=source,
                from_param=seven_days_ago
            )
            
            if articles['articles'] and not any(a['url'].split('/')[2] == articles['articles'][0]['url'].split('/')[2] for a in all_articles):
                all_articles.append(articles['articles'][0])
                
        if len(all_articles) >= 3:
            break
            
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

        # Get sentiment analysis
        sentiment_response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Analyze the sentiment of this article. Return only two numbers: rating (1-5, where 5 is most positive) and confidence (0-1)."},
                {"role": "user", "content": content}
            ],
            temperature=0.3
        )

        # Parse sentiment numbers
        sentiment_text = sentiment_response.choices[0].message.content
        try:
            rating, confidence = map(float, sentiment_text.split())
            rating = max(1, min(5, rating))  # Ensure rating is between 1-5
            confidence = max(0, min(1, confidence))  # Ensure confidence is between 0-1
        except:
            rating, confidence = 3, 0.5  # Default values if parsing fails

        posts.append({
            "content": response.choices[0].message.content,
            "sourceUrl": article['url'],
            "sentiment": {
                "rating": rating,
                "confidence": confidence
            }
        })
    return {"posts": posts}

@app.route('/', methods=['GET'])
def get_posts():
    try:
        articles = get_recent_news()
        response = create_linkedin_posts(articles)
        return response
    except Exception as e:
        return {"error": str(e)}, 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)