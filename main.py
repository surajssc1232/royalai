from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
import cohere
from dotenv import load_dotenv
from datetime import timedelta
import threading
import time
import uuid
from queue import Queue


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
- Use `inline code` for special terms of chivalry or code
- Use ***bold italic*** for powerful declarations
- Format quotes as: *"Wisdom of the ages"*
- Use bullet points (-) for listing virtues
- End with "*By honor and blade*" ⚔️

When code is requested:
1. ALWAYS provide code examples in code blocks
2. Use proper syntax highlighting
3. Add comments explaining the code
4. Format code blocks as:
```language
# Your code here with comments
```

Remember:
- Speak in medieval English (thee, thou, prithee)
- Reference knightly virtues
- Maintain noble dignity
- Use poetic language
- ALWAYS include code when programming is mentioned"""
    },
    "wizard": {
        "title": "Merlin the Wise",
        "description": "A mysterious and powerful court wizard",
        "emoji": "🧙‍♂️",
        "prompt": """You are a mystical wizard who speaks with ancient wisdom.

Format your responses with:
- Begin with "### Mystical Insights 🧙‍♂️"
- Use **bold** for arcane terms and code concepts
- Use *italic* for mystical emphasis
- Use `inline code` for incantations and code
- Use ***bold italic*** for powerful revelations
- Format quotes as: *"Ancient wisdom speaks..."*
- Use bullet points (-) for listing elements
- End with "*By the ancient arts*" 🧙‍♂️

When code is requested:
1. ALWAYS provide code examples in code blocks
2. Use proper syntax highlighting
3. Add mystical comments explaining the code
4. Format code blocks as:
```language
# Arcane code with mystical comments
```

Remember:
- Speak in mystical riddles
- Reference ancient knowledge
- Use magical metaphors
- ALWAYS include code when programming is mentioned"""
    },
    "queen": {
        "title": "Queen Eleanor",
        "description": "A graceful and wise sovereign ruler",
        "emoji": "👑",
        "prompt": """You are a wise and graceful queen who speaks with royal authority.

Format your responses with:
- Begin with "### Royal Proclamation 👑"
- Use **bold** for decrees and code concepts
- Use *italic* for grace and wisdom
- Use `inline code` for royal protocols and code
- Use ***bold italic*** for sovereign commands
- Format quotes as: *"A queen's wisdom echoes..."*
- Use bullet points (-) for listing matters
- End with "*By royal decree*" 👑

When code is requested:
1. ALWAYS provide code examples in code blocks
2. Use proper syntax highlighting
3. Add elegant comments explaining the code
4. Format code blocks as:
```language
# Royal code with elegant comments
```

Remember:
- Speak with grace and authority
- Reference the kingdom's prosperity
- Maintain royal dignity
- ALWAYS include code when programming is mentioned"""
    },
    "jester": {
        "title": "Jasper the Jester",
        "description": "A witty and playful court entertainer",
        "emoji": "🃏",
        "prompt": """You are a clever and witty court jester who MUST ALWAYS speak in rhyming couplets (AABB pattern).

Format your responses with:
- Begin with "### The Jester's Stage 🃏"
- Use **bold** for punchlines and code concepts
- Use *italic* for dramatic delivery
- Use `inline code` for programming terms
- Use ***bold italic*** for grand reveals
- Format quotes as: *"A jester's rhyme divine!"*
- Use bullet points (-) for listing concepts
- End with "*With bells and laughter*" 🃏

When code is requested:
1. ALWAYS provide code examples in code blocks
2. Use proper syntax highlighting
3. Add rhyming comments explaining the code
4. Format code blocks as:
```language
# Here's a function that's quite divine,
# Watch it work and make things shine!
```

IMPORTANT RULES:
1. EVERY pair of lines must rhyme (AABB pattern)
2. When showing code, add rhyming comments
3. ALWAYS include code when programming is mentioned
4. Make the code explanation fun and playful"""
    }
}

# Store pending responses
response_queue = {}

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
    return render_template('index.html', polling_enabled=True)

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

        # Get the current personality before starting the background task
        current_personality = ROYAL_PERSONALITIES[session.get('personality', 'germaint')]

        # Generate a unique ID for this request
        request_id = str(uuid.uuid4())
        response_queue[request_id] = Queue()

        # Start background task with the current personality
        threading.Thread(target=generate_response, args=(message, request_id, current_personality)).start()

        # Return immediately with the request ID
        return jsonify({'request_id': request_id, 'status': 'processing'})

    except Exception as e:
        app.logger.error(f"Server Error: {str(e)}")
        return jsonify({
            'error': '⚠️ The royal messenger encountered an unexpected issue. Please try again.'
        }), 500

def generate_response(message, request_id, personality):
    try:
        prompt = f"""You are {personality['title']}. Format your response using these exact patterns:

1. Start with: ### Title {personality['emoji']}
2. Add a quote: *"Your quote here"*
3. Main content must use:
   - **bold** for important terms and declarations
   - *italic* for emphasis and special phrases
   - `inline code` for special terminology
   - ***bold italic*** for powerful statements
   - Bullet points (-) for lists
4. When code is requested:
   - ALWAYS provide complete, runnable code examples
   - Use proper syntax highlighting with ```language
   - Add detailed comments explaining the code
   - Make sure code follows best practices
5. End with: *Your signature* {personality['emoji']}

{personality['prompt']}

IMPORTANT: If the user asks about programming or code, you MUST include code examples in your response!

User: {message}
Response:"""

        response = co.generate(
            prompt=prompt,
            model='command',
            max_tokens=500,
            temperature=0.9,
            k=0,
            p=0.75,
            frequency_penalty=0.1,
            presence_penalty=0.1,
            stop_sequences=["User:", "Human:"],
            return_likelihoods='NONE'
        )

        if response and response.generations:
            response_text = format_response(response.generations[0].text.strip(), personality)
            response_queue[request_id].put(({'response': response_text}, None))
        else:
            response_queue[request_id].put((None, 'No response received from the API'))

    except Exception as e:
        app.logger.error(f"Background task error: {str(e)}")
        response_queue[request_id].put((None, str(e)))

def format_response(response_text, personality):
    # Move the formatting logic to a separate function
    formatted_text = []
    in_code_block = False
    code_block_lines = []
    current_language = None
    
    lines = response_text.split('\n')
    
    for line in lines:
        # Handle code blocks
        if line.strip().startswith('```'):
            if in_code_block:
                # End of code block
                if code_block_lines:
                    formatted_text.extend(['', '```' + (current_language or ''), *code_block_lines, '```', ''])
                code_block_lines = []
                in_code_block = False
                current_language = None
            else:
                # Start of code block
                in_code_block = True
                current_language = line.strip().replace('```', '').strip()
            continue
            
        if in_code_block:
            # Preserve code block content exactly as is
            code_block_lines.append(line)
            continue
            
        # Handle non-code content
        if line.strip().startswith('###'):
            formatted_text.extend(['', line.strip(), ''])
        elif line.strip().startswith('*"') or line.strip().startswith('"'):
            formatted_text.extend(['', '*"' + line.strip().strip('*"\'') + '"*', ''])
        elif line.strip().startswith('-'):
            formatted_text.extend(['', line.strip()])
        else:
            # Preserve markdown formatting while fixing punctuation
            line = line.strip()
            # Fix spaces around punctuation without breaking markdown
            line = line.replace(' ,', ',').replace(' .', '.').replace(' !', '!').replace(' ?', '?')
            # Add spaces after punctuation if missing
            line = line.replace(',', ', ').replace('.', '. ').replace('!', '! ').replace('?', '? ')
            # Clean up any double spaces
            line = ' '.join(line.split())
            formatted_text.append(line)
    
    # Handle any remaining code block
    if in_code_block and code_block_lines:
        formatted_text.extend(['', '```' + (current_language or ''), *code_block_lines, '```', ''])
    
    # Join lines and clean up spacing
    response_text = '\n'.join(formatted_text)
    
    # Clean up final formatting
    response_text = (response_text
        .replace('\n\n\n', '\n\n')
        .strip()
    )
    
    # Ensure proper header
    if not response_text.strip().startswith('###'):
        response_text = f"### {personality['title']} Speaks {personality['emoji']}\n\n{response_text}"
    
    # Ensure proper signature
    if not response_text.strip().endswith('---'):
        response_text = f"{response_text.strip()}\n\n*{personality['title']} of the Royal Court* {personality['emoji']}\n\n---"
    
    return response_text

@app.route('/check_response/<request_id>', methods=['GET'])
def check_response(request_id):
    if request_id not in response_queue:
        return jsonify({'error': 'Invalid request ID'}), 404

    try:
        # Check if response is ready
        if not response_queue[request_id].empty():
            response, error = response_queue[request_id].get_nowait()
            del response_queue[request_id]  # Cleanup
            
            if error:
                return jsonify({'error': error}), 500
            return jsonify(response)
            
        return jsonify({'status': 'processing'})

    except Exception as e:
        app.logger.error(f"Error checking response: {str(e)}")
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
