
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
    <title>German AI News Curator</title>
    <style>
        body { max-width: 800px; margin: 0 auto; padding: 20px; font-family: Arial, sans-serif; }
        .chat-box { margin: 20px 0; padding: 20px; border: 1px solid #ddd; border-radius: 5px; }
        textarea { width: 100%; height: 50px; margin: 10px 0; }
        button { background: #0066cc; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
        .response { margin-top: 20px; padding: 10px; background: #f5f5f5; border-radius: 5px; white-space: pre-line; }
    </style>
</head>
<body>
    <h1>German AI News Curator</h1>
    <div class="chat-box">
        <form method="POST">
            <textarea name="prompt" placeholder="Optional: Enter specific AI topics to search for in German news..."></textarea><br>
            <button type="submit">Send</button>
        </form>
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
    if request.method == 'POST':
        user_prompt = request.form.get('prompt', '').strip()
        
        system_prompt = """You are an AI news curator specializing in German tech news.
        Find 3 significant AI-related news stories from German news outlets from the past 7 days.
        Format each story in German with:
        1. Headline
        2. Short summary (2-3 sentences)
        3. Source and date
        4. URL (use plausible URLs from real German tech news sites)
        
        Separate stories with '---'"""
        
        if user_prompt:
            user_message = f"Find 3 German news stories about AI focusing on: {user_prompt}"
        else:
            user_message = "Find 3 interesting German news stories about AI from the past week"
            
        chat_response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
        )
        response = chat_response.choices[0].message.content
    
    return render_template_string(HTML_TEMPLATE, response=response)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)
