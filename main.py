
import openai
import os
import sys
from flask import Flask, request, render_template_string

app = Flask(__name__)

# OpenAI API key check
openai.api_key = os.environ.get('OPENAI_API_KEY')
if not openai.api_key:
    sys.stderr.write("""
    You haven't set up your API key yet.
    
    If you don't have an API key yet, visit:
    
    https://platform.openai.com/signup

    1. Make an account or sign in
    2. Click "View API Keys" from the top right menu.
    3. Click "Create new secret key"

    Then, open the Secrets Tool and add OPENAI_API_KEY as a secret.
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
        button { background: #0066cc; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
        .response { margin-top: 20px; padding: 10px; background: #f5f5f5; border-radius: 5px; white-space: pre-line; }
    </style>
</head>
<body>
    <h1>Latest German AI News</h1>
    <div class="news-box">
        {% if response %}
        <div class="response">
            <strong>Response:</strong><br>
            {{ response }}
        </div>
        {% endif %}
    </div>
</body>
</html>
'''

@app.route('/', methods=['GET', 'POST'])
def chat():
    response = None
    try:
        system_prompt = """You are a German AI news curator. Look up 3 headline news stories about Artifical Intelligence from the past 7 days from German news sources. Format in German with:
        
        For each story:
        Überschrift: [headline]
        Zusammenfassung: [2-3 sentence summary]
        Quelle: [German news source]
        Datum: [recent date]
        URl: [URL]
        
        Separate stories with '---'"""
        
        chat_response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Generate 3 current German AI news stories"}
            ],
            temperature=0.7,
            max_tokens=1000
        )
        response = chat_response.choices[0].message.content
    except Exception as e:
        response = f"Error: {str(e)}"
    
    return render_template_string(HTML_TEMPLATE, response=response)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)
