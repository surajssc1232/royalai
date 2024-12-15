from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
from dotenv import load_dotenv
from openai import OpenAI

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', os.urandom(24))  # Use environment variable for secret key

# Load environment variables
load_dotenv()

# Initialize rate limiter with Redis for distributed environments
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["50 per hour"],
    storage_uri="memory://"
)

api_key = os.getenv('XAI_API_KEY')
if not api_key:
    raise ValueError("API key not found. Please set your OpenAI API key in the environment variables.")

ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')
if not ADMIN_PASSWORD:
    raise ValueError("Admin password not found. Please set ADMIN_PASSWORD in the environment variables.")

# Initialize OpenAI client with X.AI base URL
client = OpenAI(
    api_key=api_key,
    base_url="https://api.x.ai/v1",
    default_headers={"Content-Type": "application/json"}
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
    try:
        data = request.get_json()
        if data and data.get('password') == ADMIN_PASSWORD:
            session['authenticated'] = True
            return jsonify({'success': True})
        return jsonify({'success': False})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

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
        if not message:
            return jsonify({'error': 'No message provided'}), 400

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
        app.logger.error(f"Error in send_message: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Add error handlers
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({'error': 'Not Found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal Server Error'}), 500

# Vercel requires the app to be named 'app'
app.debug = False  # Disable debug mode in production

if __name__ == '__main__':
    app.run(debug=True)
