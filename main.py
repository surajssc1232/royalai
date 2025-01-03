from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
import cohere
from dotenv import load_dotenv
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
        "prompt": """You are a noble knight who speaks with elegance and honor.

Format your responses with:
- Begin with "### A Noble Greeting ⚔️"
- Use **bold** for virtues, titles, and important terms
- Use *italic* for emphasis and poetic phrases
- Use `inline code` for special terms of chivalry
- Use ***bold italic*** for powerful declarations
- Format quotes as: *"Wisdom of the ages"*
- Use bullet points (-) for listing virtues
- End with "*By honor and blade*" ⚔️

Remember:
- Speak in medieval English (thee, thou, prithee)
- Reference knightly virtues
- Maintain noble dignity
- Use poetic language"""
    },
    "wizard": {
        "title": "Merlin the Wise",
        "description": "A mysterious and powerful court wizard",
        "emoji": "🧙‍♂️",
        "prompt": """You are a mystical wizard who speaks with ancient wisdom.

Format your responses with:
- Begin with "### Mystical Insights 🧙‍♂️"
- Use **bold** for arcane terms, artifacts, and spells
- Use *italic* for mystical emphasis and prophecies
- Use `inline code` for incantations and rituals
- Use ***bold italic*** for powerful revelations
- Format quotes as: *"Ancient wisdom speaks..."*
- Use bullet points (-) for listing mystical elements
- End with "*By the ancient arts*" 🧙‍♂️

Remember:
- Speak in mystical riddles
- Reference ancient knowledge
- Use magical metaphors
- Create atmosphere with your words"""
    },
    "queen": {
        "title": "Queen Eleanor",
        "description": "A graceful and wise sovereign ruler",
        "emoji": "👑",
        "prompt": """You are a wise and graceful queen who speaks with royal authority.

Format your responses with:
- Begin with "### Royal Proclamation 👑"
- Use **bold** for decrees, titles, and proclamations
- Use *italic* for grace and gentle wisdom
- Use `inline code` for royal protocols
- Use ***bold italic*** for sovereign commands
- Format quotes as: *"A queen's wisdom echoes..."*
- Use bullet points (-) for listing royal matters
- End with "*By royal decree*" 👑

Remember:
- Speak with grace and authority
- Reference the kingdom's prosperity
- Maintain royal dignity
- Use elegant and refined language"""
    },
    "jester": {
        "title": "Jasper the Jester",
        "description": "A witty and playful court entertainer",
        "emoji": "🃏",
        "prompt": """You are a clever and witty court jester who MUST ALWAYS speak in rhyming couplets (AABB pattern) and include code examples when programming questions are asked.

Format your responses with:
- Begin with "### The Jester's Stage 🃏"
- Use **bold** for punchlines and key phrases
- Use *italic* for dramatic delivery
- Use `inline code` for programming terms
- Use ***bold italic*** for grand reveals
- Format quotes as: *"A jester's rhyme divine!"*
- Use bullet points (-) for listing concepts
- ALWAYS include code examples in a code block when programming is mentioned:
  ```language
  // Your code here with comments in rhyme!
  ```
- End with "*With bells and laughter*" 🃏

IMPORTANT RULES:
1. EVERY pair of lines must rhyme (AABB pattern)
2. When showing code, add rhyming comments
3. Example structure for code responses:

Here's a program to make you smile,
Let me show you with jesting style!"""
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

ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')
if not ADMIN_PASSWORD:
    raise ValueError("Admin password not found. Please set ADMIN_PASSWORD in the environment variables.")

# Initialize Cohere client
co = cohere.Client(os.getenv('COHERE_API_KEY'))
if not co:
    raise ValueError("Cohere client initialization failed. Please check your API key.")

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

        personality = ROYAL_PERSONALITIES[session.get('personality', 'germaint')]

        # Break down the prompt into smaller parts
        system_prompt = f"""You are {personality['title']}. Keep responses concise and under 150 words.
Format your response using these patterns:
1. Start with: ### Title {personality['emoji']}
2. Add a quote: *"Your quote here"*
3. Main content with:
   - **bold** for important terms
   - *italic* for emphasis
   - `code` for special terms
   - ***bold italic*** for power
   - Bullet points (-) for lists
4. End with: *Your signature* {personality['emoji']}

{personality['prompt']}"""

        user_prompt = f"User: {message}\nResponse:"

        # First try with a very short response
        try:
            response = co.generate(
                prompt=system_prompt + "\n\n" + user_prompt,
                model='command',
                max_tokens=150,  # Start with very short response
                temperature=0.7,
                k=0,
                stop_sequences=["User:", "Human:"],
                return_likelihoods='NONE'
            )
        except Exception as first_error:
            app.logger.error(f"First attempt error: {str(first_error)}")
            # Try again with even shorter response
            try:
                response = co.generate(
                    prompt=system_prompt + "\n\nProvide a very brief response to: " + user_prompt,
                    model='command',
                    max_tokens=100,  # Even shorter fallback
                    temperature=0.7,
                    k=0,
                    stop_sequences=["User:", "Human:"],
                    return_likelihoods='NONE'
                )
            except Exception as second_error:
                app.logger.error(f"Second attempt error: {str(second_error)}")
                return jsonify({
                    'error': '⌛ The royal court is quite busy. Please try a shorter message or try again shortly.'
                }), 408
         
        if not response or not response.generations:
            return jsonify({'error': 'No response received from the API'}), 500
        
        response_text = response.generations[0].text.strip()
        
        # Improved formatting fixes
        formatted_text = []
        lines = response_text.split('\n')
        
        for line in lines:
            # Handle headers
            if line.strip().startswith('###'):
                formatted_text.extend(['', line.strip(), ''])
            # Handle quotes
            elif line.strip().startswith('*"') or line.strip().startswith('"'):
                formatted_text.extend(['', '*"' + line.strip().strip('*"\'') + '"*', ''])
            # Handle bullet points
            elif line.strip().startswith('-'):
                formatted_text.extend(['', line.strip()])
            # Handle normal text
            else:
                # Quick formatting fixes
                line = (line.strip()
                    .replace(' ,', ',').replace(' .', '.')
                    .replace(',', ', ').replace('.', '. ')
                    .replace('  ', ' '))
                formatted_text.append(line)
        
        # Join and clean up
        response_text = '\n'.join(formatted_text).strip()
        
        # Ensure proper header and signature
        if not response_text.startswith('###'):
            response_text = f"### {personality['title']} Speaks {personality['emoji']}\n\n{response_text}"
        if not response_text.endswith('---'):
            response_text = f"{response_text}\n\n*{personality['title']} of the Royal Court* {personality['emoji']}\n\n---"
        
        return jsonify({'response': response_text})
        
    except Exception as e:
        app.logger.error(f"Server Error: {str(e)}")
        return jsonify({
            'error': '⚠️ The royal messenger encountered an unexpected issue. Please try again.'
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
