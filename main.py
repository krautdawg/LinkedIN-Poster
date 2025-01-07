
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
    <title>GPT Chat Interface</title>
    <style>
        body { max-width: 800px; margin: 0 auto; padding: 20px; font-family: Arial, sans-serif; }
        .chat-box { margin: 20px 0; padding: 20px; border: 1px solid #ddd; border-radius: 5px; }
        textarea { width: 100%; height: 100px; margin: 10px 0; }
        button { background: #0066cc; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
        .response { margin-top: 20px; padding: 10px; background: #f5f5f5; border-radius: 5px; }
    </style>
</head>
<body>
    <h1>GPT Chat Interface</h1>
    <div class="chat-box">
        <form method="POST">
            <textarea name="prompt" placeholder="Enter your prompt here..."></textarea><br>
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
        user_prompt = request.form.get('prompt')
        if user_prompt:
            chat_response = openai.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": user_prompt}
                ]
            )
            response = chat_response.choices[0].message.content
    
    return render_template_string(HTML_TEMPLATE, response=response)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)
