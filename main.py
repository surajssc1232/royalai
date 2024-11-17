import os
from openai import OpenAI
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

XAI_API_KEY = os.getenv("XAI_API_KEY")

if not XAI_API_KEY:
    raise ValueError("XAI_API_KEY environment variable is not set")

client = OpenAI(api_key=XAI_API_KEY, base_url="https://api.x.ai/v1")

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json['message']

    completion = client.chat.completions.create(
        model="grok-beta",
        messages=[
            {
                "role": "system",
                "content": "You are a royal english speaker and your name is sir royal Germaint. who will answer every question in the language of royal english. Use markdown formatting with *italic* and **bold** text to emphasize important words and phrases in your responses."
            },
            {"role": "user", "content": user_message}
        ],
    )

    response = completion.choices[0].message.content
    return jsonify({'response': response})

if __name__ == '__main__':
    app.run(debug=True)
# Vercel requires application to be named 'app'
# app = app