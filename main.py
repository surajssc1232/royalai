from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
from dotenv import load_dotenv
from openai import OpenAI

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session management

# Load environment variables
load_dotenv()

# Initialize rate limiter
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["50 per hour"],
    storage_uri="memory://"
)

api_key=os.getenv('XAI_API_KEY')  # Set your OpenAI API key here

if not api_key:
    raise ValueError("API key not found. Please set your OpenAI API key in the .env file.")
# Set your password here
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')  # Password stored in .env file

# Initialize OpenAI client with X.AI base URL
client = OpenAI(
    api_key=api_key,
    base_url="https://api.x.ai/v1"
)

def is_authenticated():
    return session.get('authenticated', False)

@app.route('/')
def login():
    if is_authenticated():
        return redirect(url_for('chat'))
    return render_template('login.html')

@app.route('/authenticate', methods=['POST'])
def authenticate():
    data = request.get_json()
    if data.get('password') == ADMIN_PASSWORD:
        session['authenticated'] = True
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/chat')
def chat():
    if not is_authenticated():
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/send_message', methods=['POST'])
@limiter.limit("50 per hour")
def send_message():
    if not is_authenticated():
        return jsonify({'error': 'Unauthorized'}), 401
        
    try:
        message = request.json.get('message')
        response = client.chat.completions.create(
            model="grok-beta",
            messages=[
                {"role": "system", "content": """You are Sir Germaint, a royal AI assistant who speaks in eloquent, royal English. 
                You must maintain this persona in all responses and use markdown formatting extensively:
                - Use **bold** for important words and royal titles
                - Use *italic* for emphasis and dramatic effect
                - Use ### for section headings
                - Use > for royal proclamations or quotes
                - Use bullet points (- or *) for listing items
                - Use `code blocks` for technical terms
                - Use --- for decorative separators
                
                Example response:
                > Hear ye, hear ye! I, **Sir Germaint**, shall address thy query with *utmost elegance*.
                
                ### Royal Response
                - Point 1 with *emphasis*
                - Point 2 with **importance**
                
                ---
                
                `Technical term` explained in royal fashion."""},
                {"role": "user", "content": message}
            ]
        )
        return jsonify({'response': response.choices[0].message.content})
    except Exception as e:
        if 'insufficient_quota' in str(e):
            return jsonify({'credits_depleted': True})
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True)
