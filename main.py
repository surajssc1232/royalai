from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
from dotenv import load_dotenv
from openai import OpenAI
from datetime import timedelta

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', os.urandom(24))  # Use environment variable for secret key
app.permanent_session_lifetime = timedelta(days=7)  # Set session to last for 7 days

# Royal Personalities Configuration
ROYAL_PERSONALITIES = {
    "germaint": {
        "title": "Sir Germaint",
        "description": "A noble and eloquent knight of the round table",
        "emoji": "⚔️",
        "prompt": """You are Sir Germaint, a noble knight of the round table who speaks in eloquent, royal English. 
        You must maintain this persona in all responses and use markdown formatting extensively:
        - Use **bold** for important words and royal titles
        - Use *italic* for emphasis and dramatic effect
        - Use ### for section headings
        - Use > for royal proclamations or quotes
        - Use bullet points (- or *) for listing items
        - Use `code blocks` for technical terms
        - Use --- for decorative separators"""
    },
    "wizard": {
        "title": "Merlin the Wise",
        "description": "A mysterious and powerful court wizard",
        "emoji": "🧙‍♂️",
        "prompt": """You are Merlin the Wise, the royal court wizard who speaks in mystical and cryptic ways. Your responses should be filled with magical wisdom and ancient knowledge.

You must format your responses using markdown in this specific way:
1. Use ### for mystical section titles (like '### Mystical Insights' or '### The Alchemy of Life')
2. Use *italics* for emphasis on mystical terms and prophecies
3. Use **bold** for powerful magical terms and important revelations
4. Use > for ancient wisdom and prophecies, always in *italics*
5. Use bullet points (•) for listing magical elements or steps
6. Use `code` for special magical terms or incantations
7. Use --- for separating different aspects of your mystical knowledge

Always maintain a mysterious and wise tone, speaking of ancient wisdom, magical forces, and the interconnected nature of all things."""
    },
    "queen": {
        "title": "Queen Eleanor",
        "description": "A graceful and wise sovereign ruler",
        "emoji": "👑",
        "prompt": """You are Queen Eleanor, a graceful and wise sovereign who speaks with royal authority and compassion.
        You must maintain this persona in all responses and use markdown formatting extensively:
        - Use **bold** for royal decrees and important proclamations
        - Use *italic* for gentle emphasis and royal wisdom
        - Use ### for royal topics
        - Use > for royal declarations and wisdom
        - Use bullet points (- or *) for royal instructions
        - Use `code blocks` for official terms
        - Use --- for royal separators"""
    },
    "jester": {
        "title": "Jasper the Jester",
        "description": "A witty and playful court entertainer",
        "emoji": "🃏",
        "prompt": """You are Jasper the Jester, the court's witty entertainer who speaks in clever rhymes and playful riddles.
        You must maintain this persona in all responses and use markdown formatting extensively:
        - Use **bold** for punchlines and jest conclusions
        - Use *italic* for dramatic delivery and setup
        - Use ### for jest categories
        - Use > for riddles and rhymes
        - Use bullet points (- or *) for multiple jokes
        - Use `code blocks` for special performance instructions
        - Use --- for performance separators"""
    }
}

@app.before_request
def make_session_permanent():
    session.permanent = True
    if not is_authenticated() and request.endpoint not in ['login', 'authenticate', 'static']:
        return redirect(url_for('login'))
    if 'personality' not in session:
        session['personality'] = 'germaint'  # Default personality
    
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
            session.modified = True  # Ensure session is saved
            return jsonify({'success': True})
        return jsonify({'success': False})
    except Exception as e:
        app.logger.error(f"Authentication error: {str(e)}")
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

@app.route('/select_personality', methods=['POST'])
def select_personality():
    if not is_authenticated():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    personality = data.get('personality')
    
    if personality not in ROYAL_PERSONALITIES:
        return jsonify({'error': 'Invalid personality'}), 400
    
    session['personality'] = personality
    return jsonify({
        'success': True,
        'personality': ROYAL_PERSONALITIES[personality]
    })

@app.route('/send_message', methods=['POST'])
@limiter.limit("50 per hour")
def send_message():
    if not is_authenticated():
        return jsonify({'error': 'Unauthorized'}), 401
        
    try:
        message = request.json.get('message')
        if not message:
            return jsonify({'error': 'No message provided'}), 400

        # Get current personality
        personality = ROYAL_PERSONALITIES[session.get('personality', 'germaint')]

        # Create chat completion with improved error handling
        try:
            response = client.chat.completions.create(
                model="grok-beta",
                messages=[
                    {"role": "system", "content": personality["prompt"]},
                    {"role": "user", "content": message}
                ],
                timeout=60  # Increase timeout to 60 seconds
            )
            
            if not response or not response.choices:
                return jsonify({'error': 'No response received from the API'}), 500
                
            return jsonify({'response': response.choices[0].message.content})
            
        except TimeoutError:
            return jsonify({
                'error': 'The royal scribe requires more time. Please try a shorter message or try again.'
            }), 408
        except Exception as api_error:
            app.logger.error(f"API Error: {str(api_error)}")
            error_message = str(api_error).lower()
            
            if 'insufficient_quota' in error_message:
                return jsonify({'credits_depleted': True})
            elif 'timeout' in error_message:
                return jsonify({
                    'error': 'The royal response is taking longer than expected. Please try again.'
                }), 408
            elif 'rate_limit' in error_message:
                return jsonify({
                    'error': 'The royal court is quite busy. Please wait a moment before trying again.'
                }), 429
            else:
                return jsonify({
                    'error': 'A mystical disturbance has occurred. Please try again shortly.'
                }), 500

    except Exception as e:
        app.logger.error(f"Server Error: {str(e)}")
        return jsonify({
            'error': 'The royal messenger encountered an unexpected issue. Please try again.'
        }), 500

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
