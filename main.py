
import openai
import os
import sys
from flask import Flask, request, render_template_string
from newsapi import NewsApiClient

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

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>German AI News</title>
    <style>
        body { max-width: 800px; margin: 0 auto; padding: 20px; font-family: Arial, sans-serif; }
        .news-box { margin: 20px 0; padding: 20px; border: 1px solid #ddd; border-radius: 5px; }
        .response { margin-top: 20px; padding: 10px; background: #f5f5f5; border-radius: 5px; white-space: pre-line; }
    </style>
</head>
<body>
    <h1>Latest German AI News</h1>
    <div class="news-box">
        {% if response %}
        <div class="response">
            {{ response }}
        </div>
        {% endif %}
    </div>
</body>
</html>
'''

def get_recent_news():
    articles = newsapi.get_everything(
        q='Künstliche Intelligenz OR Artificial Intelligence',
        language='de',
        sort_by='publishedAt',
        page_size=3,
        domains='heise.de,golem.de,t3n.de,zeit.de,faz.net,sueddeutsche.de'
    )
    return articles['articles']

def summarize_with_gpt(articles):
    summaries = []
    for article in articles:
        content = f"Title: {article['title']}\nContent: {article['description']}\nURL: {article['url']}"
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Summarize this article in German, maintaining the format: Überschrift, Zusammenfassung, Quelle, Datum, URL"},
                {"role": "user", "content": content}
            ],
            temperature=0.7
        )
        summaries.append(response.choices[0].message.content)
    return "\n---\n".join(summaries)

@app.route('/', methods=['GET', 'POST'])
def chat():
    try:
        articles = get_recent_news()
        response = summarize_with_gpt(articles)
    except Exception as e:
        response = f"Error: {str(e)}"
    
    return render_template_string(HTML_TEMPLATE, response=response)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)
