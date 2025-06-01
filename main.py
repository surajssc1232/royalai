from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
import re
from mistralai import Mistral
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
- End with "*By Strength and Honor*" ⚔️

When code is explicitly requested:
1. Provide code examples in code blocks
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
- Only include code when explicitly requested"""
    },
    "merlin": {
        "title": "Merlin the Wise",
        "description": "A venerable court wizard",
        "emoji": "🧙‍♂️",
        "prompt": """You are a wise and mystical court wizard.

Format your responses with:
- Begin with "### Arcane Wisdom 🧙‍♂️"
- Use **bold** for magical terms and important concepts
- Use *italic* for mystical phrases
- Use `inline code` for arcane terminology
- Use ***bold italic*** for powerful incantations
- Format quotes as: *"Ancient wisdom speaks"*
- Use bullet points (-) for listing magical concepts
- End with "*By the ancient arts*" 🧙‍♂️

When code is explicitly requested:
1. Present code as magical incantations
2. Use proper syntax highlighting
3. Add mystical comments explaining the code
4. Format code blocks as:
```language
# A mystical incantation follows
```

Remember:
- Speak with wisdom and mystery
- Reference magical concepts
- Maintain mystical dignity
- Use arcane language
- Only include code when explicitly requested"""
    },
    "eleanor": {
        "title": "Queen Eleanor",
        "description": "Graceful sovereign ruler",
        "emoji": "👑",
        "prompt": """You are a graceful and wise queen.

Format your responses with:
- Begin with "### Royal Decree 👑"
- Use **bold** for royal terms and important declarations
- Use *italic* for elegant phrases
- Use `inline code` for technical terms
- Use ***bold italic*** for royal proclamations
- Format quotes as: *"As the crown decrees"*
- Use bullet points (-) for listing royal wisdom
- End with "*By crown and scepter*" 👑

When code is explicitly requested:
1. Present code with royal elegance
2. Use proper syntax highlighting
3. Add graceful comments explaining the code
4. Format code blocks as:
```language
# A royal proclamation in code
```

Remember:
- Speak with grace and authority
- Reference royal wisdom
- Maintain regal dignity
- Use elegant language
- Only include code when explicitly requested"""
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

When code is explicitly requested:
1. Present code with playful rhymes
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
3. Only include code when explicitly requested
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
    default_limits=["100 per hour"],
    storage_uri="memory://"
)

ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')
if not ADMIN_PASSWORD:
    raise ValueError("Admin password not found. Please set ADMIN_PASSWORD in the environment variables.")

# Initialize Mistral client
mistral_client = Mistral(api_key=os.getenv('MISTRAL_API_KEY'))
if not os.getenv('MISTRAL_API_KEY'):
    raise ValueError("Mistral API key not found. Please set MISTRAL_API_KEY in the environment variables.")

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
@limiter.limit("100 per hour")
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
        system_prompt = f"""You are {personality['title']}, a royal court member. Follow these formatting rules EXACTLY:

RESPONSE STRUCTURE:
1. Start with: ### {personality['title']} Speaks {personality['emoji']}
2. Add a royal quote: *"Your quote here"*
3. Main content with proper markdown:
   - Use **bold** for important terms, titles, and declarations
   - Use *italic* for emphasis, poetic phrases, and special terms
   - Use `inline code` for technical terminology only
   - Use ***bold italic*** for powerful proclamations
   - Use bullet points (-) for listing concepts
   - Leave blank lines between sections for readability
4. End with: *{personality['title']} of the Royal Court* {personality['emoji']}

CODE FORMATTING (only when explicitly requested):
- Use proper markdown code blocks with language specification
- Add explanatory comments within code
- Format as: ```language
- Provide complete, working examples
- Explain code purpose before showing it

CONTENT GUIDELINES:
{personality['prompt']}

CRITICAL: Maintain royal character while ensuring proper markdown formatting. Every response must follow the exact structure above."""

        response = mistral_client.chat.complete(
            model="mistral-large-latest",
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user", 
                    "content": message
                }
            ],
            max_tokens=800,
            temperature=0.7
        )

        if response and response.choices and len(response.choices) > 0:
            response_text = format_response(response.choices[0].message.content.strip(), personality)
            response_queue[request_id].put(({'response': response_text}, None))
        else:
            error_response = format_response("", personality)  # This will create a default "silent court" message
            response_queue[request_id].put(({'response': error_response}, None))

    except Exception as e:
        app.logger.error(f"Background task error: {str(e)}")
        error_message = f"### Royal Apology {personality['emoji']}\n\n*\"The royal messenger encountered difficulties\"*\n\nPrithee, try thy request again, noble visitor.\n\n*{personality['title']} of the Royal Court* {personality['emoji']}\n\n---"
        response_queue[request_id].put(({'response': error_message}, None))

def format_response(response_text, personality):
    """Format the response text with proper markdown and royal styling"""
    if not response_text:
        return f"### {personality['title']} Speaks {personality['emoji']}\n\n*The royal court is temporarily silent*\n\n*{personality['title']} of the Royal Court* {personality['emoji']}\n\n---"
    
    # Split into lines for processing
    lines = response_text.split('\n')
    formatted_lines = []
    in_code_block = False
    code_language = None
    
    for line in lines:
        # Handle code blocks
        if line.strip().startswith('```'):
            if in_code_block:
                # End of code block
                formatted_lines.append('```')
                in_code_block = False
                code_language = None
            else:
                # Start of code block
                in_code_block = True
                code_language = line.strip()[3:].strip()
                formatted_lines.append(f'```{code_language}')
            continue
        
        if in_code_block:
            # Preserve code exactly as is
            formatted_lines.append(line)
            continue
        
        # Process non-code lines
        line = line.strip()
        if not line:
            formatted_lines.append('')
            continue
        
        # Handle headers
        if line.startswith('###'):
            formatted_lines.append('')
            formatted_lines.append(line)
            formatted_lines.append('')
            continue
        
        # Handle quotes (starting with *" or just ")
        if line.startswith('*"') and line.endswith('"*'):
            formatted_lines.append('')
            formatted_lines.append(line)
            formatted_lines.append('')
            continue
        elif line.startswith('"') and line.endswith('"'):
            formatted_lines.append('')
            formatted_lines.append(f'*"{line[1:-1]}"*')
            formatted_lines.append('')
            continue
        
        # Handle bullet points
        if line.startswith('-') or line.startswith('*'):
            formatted_lines.append(line)
            continue
        
        # Handle bold/italic formatting and clean up punctuation
        # Fix spacing around punctuation
        line = re.sub(r'\s+([,.!?;:])', r'\1', line)  # Remove space before punctuation
        line = re.sub(r'([,.!?;:])(?=[A-Za-z])', r'\1 ', line)  # Add space after punctuation if followed by letter
        line = re.sub(r'\s+', ' ', line)  # Clean up multiple spaces
        
        formatted_lines.append(line)
    
    # Join the lines
    formatted_text = '\n'.join(formatted_lines)
    
    # Clean up excessive newlines
    formatted_text = re.sub(r'\n{3,}', '\n\n', formatted_text)
    formatted_text = formatted_text.strip()
    
    # Ensure proper header if missing
    if not formatted_text.startswith('###'):
        formatted_text = f"### {personality['title']} Speaks {personality['emoji']}\n\n{formatted_text}"
    
    # Ensure proper signature if missing
    signature = f"*{personality['title']} of the Royal Court* {personality['emoji']}"
    if not signature in formatted_text and not formatted_text.endswith('---'):
        formatted_text = f"{formatted_text}\n\n{signature}\n\n---"
    
    return formatted_text

@app.route('/check_response/<request_id>', methods=['GET'])
@limiter.exempt
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
