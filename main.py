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
from concurrent.futures import ThreadPoolExecutor
import functools

# Load environment variables first
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', os.urandom(24))  # Use environment variable for secret key
app.permanent_session_lifetime = timedelta(days=7)  # Set session to last for 7 days

# Create a thread pool for better performance
thread_pool = ThreadPoolExecutor(max_workers=3)  # Reduced for faster response times

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

# Store pending responses and add simple cache
response_queue = {}
response_cache = {}  # Simple LRU-style cache

# Pre-compile regex patterns for better performance
REGEX_PATTERNS = {
    'excessive_newlines': re.compile(r'\n{3,}'),
    'space_before_punct': re.compile(r'\s+([,.!?;:])'),
    'space_after_punct': re.compile(r'([,.!?;:])(?=[A-Za-z])'),
    'multiple_spaces': re.compile(r'\s+'),
    'code_block_start': re.compile(r'^```(\w*)'),
    'code_block_end': re.compile(r'^```$')
}

# Cache responses to improve performance for similar queries
@functools.lru_cache(maxsize=100)
def get_cached_system_prompt(personality_title, personality_emoji, personality_prompt):
    """Cache system prompts to avoid regenerating them"""
    return f"""You are {personality_title}, a royal court member. Follow these formatting rules EXACTLY:

RESPONSE STRUCTURE:
1. Start with: ### {personality_title} Speaks {personality_emoji}
2. Add a royal quote: *"Your quote here"*
3. Main content with proper markdown:
   - Use **bold** for important terms, titles, and declarations
   - Use *italic* for emphasis, poetic phrases, and special terms
   - Use `inline code` for technical terminology only
   - Use ***bold italic*** for powerful proclamations
   - Use bullet points (-) for listing concepts
   - Leave blank lines between sections for readability
4. End with: *{personality_title} of the Royal Court* {personality_emoji}

CODE FORMATTING (only when explicitly requested):
- Use proper markdown code blocks with language specification
- Add explanatory comments within code
- Format as: ```language
- Provide complete, working examples
- Explain code purpose before showing it

CONTENT GUIDELINES:
{personality_prompt}

CRITICAL: Maintain royal character while ensuring proper markdown formatting. Every response must follow the exact structure above."""

@app.before_request
def make_session_permanent():
    session.permanent = True
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

# Initialize Mistral client
mistral_client = Mistral(api_key=os.getenv('MISTRAL_API_KEY'))
if not os.getenv('MISTRAL_API_KEY'):
    raise ValueError("Mistral API key not found. Please set MISTRAL_API_KEY in the environment variables.")

@app.route('/')
def chat():
    return render_template('index.html', polling_enabled=True)

@app.route('/select_personality', methods=['POST'])
def select_personality():
    data = request.get_json()
    personality = data.get('personality')
    
    # Debug logging
    app.logger.info(f"Personality selection request: {personality}")
    app.logger.info(f"Current session personality before: {session.get('personality', 'NOT_SET')}")
    
    if personality not in ROYAL_PERSONALITIES:
        app.logger.error(f"Invalid personality requested: {personality}")
        return jsonify({'error': 'Invalid personality'}), 400
    
    session['personality'] = personality
    session.modified = True  # Force session save
    
    # Debug logging
    app.logger.info(f"Session personality after setting: {session.get('personality')}")
    app.logger.info(f"Selected personality data: {ROYAL_PERSONALITIES[personality]['title']}")
    
    return jsonify({
        'success': True,
        'personality': ROYAL_PERSONALITIES[personality]
    })

@app.route('/send_message', methods=['POST'])
@limiter.limit("100 per hour")
def send_message():
    try:
        message = request.json.get('message')
        if not message:
            return jsonify({'error': 'No message provided'}), 400

        # Debug logging for session state
        session_personality = session.get('personality', 'NOT_SET')
        app.logger.info(f"Send message - Current session personality: {session_personality}")
        
        # Get the current personality before starting the background task
        current_personality = ROYAL_PERSONALITIES[session.get('personality', 'germaint')]
        
        # Debug logging for selected personality
        app.logger.info(f"Using personality: {current_personality['title']} ({session.get('personality', 'germaint')})")

        # Check cache first for instant responses
        cache_key = f"{current_personality['title']}:{hash(message)}"
        if cache_key in response_cache:
            cached_response = response_cache[cache_key]
            return jsonify({'response': cached_response})

        # Generate a unique ID for this request
        request_id = str(uuid.uuid4())
        response_queue[request_id] = Queue()

        # Start background task with the current personality using thread pool
        thread_pool.submit(generate_response, message, request_id, current_personality)

        # Return immediately with the request ID
        return jsonify({'request_id': request_id, 'status': 'processing'})

    except Exception as e:
        app.logger.error(f"Server Error: {str(e)}")
        return jsonify({
            'error': '⚠️ The royal messenger encountered an unexpected issue. Please try again.'
        }), 500

def generate_response(message, request_id, personality):
    try:
        # Check cache first for exact matches
        cache_key = f"{personality['title']}:{hash(message)}"
        if cache_key in response_cache:
            cached_response = response_cache[cache_key]
            response_queue[request_id].put(({'response': cached_response}, None))
            return
        
        # Use cached system prompt for better performance
        system_prompt = get_cached_system_prompt(
            personality['title'], 
            personality['emoji'], 
            personality['prompt']
        )

        response = mistral_client.chat.complete(
            model="mistral-small",  # Faster than medium model
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
            max_tokens=400,  # Further reduced tokens for faster response
            temperature=0.7
        )

        if response and response.choices and len(response.choices) > 0:
            response_text = format_response_fast(response.choices[0].message.content.strip(), personality)
            # Cache the response
            if len(response_cache) > 50:  # Simple LRU implementation
                # Remove oldest entry
                oldest_key = next(iter(response_cache))
                del response_cache[oldest_key]
            response_cache[cache_key] = response_text
            response_queue[request_id].put(({'response': response_text}, None))
        else:
            error_response = format_response_fast("", personality)  # This will create a default "silent court" message
            response_queue[request_id].put(({'response': error_response}, None))

    except Exception as e:
        app.logger.error(f"Background task error: {str(e)}")
        error_message = f"### Royal Apology {personality['emoji']}\n\n*\"The royal messenger encountered difficulties\"*\n\nPrithee, try thy request again, noble visitor.\n\n*{personality['title']} of the Royal Court* {personality['emoji']}\n\n---"
        response_queue[request_id].put(({'response': error_message}, None))

def format_response_fast(response_text, personality):
    """Optimized formatting function with pre-compiled regex patterns"""
    if not response_text:
        return f"### {personality['title']} Speaks {personality['emoji']}\n\n*The royal court is temporarily silent*\n\n*{personality['title']} of the Royal Court* {personality['emoji']}\n\n---"
    
    # Fast path: if response already has proper header, minimal processing
    if response_text.startswith('###'):
        # Just clean up excessive newlines and ensure signature
        text = REGEX_PATTERNS['excessive_newlines'].sub('\n\n', response_text)
        signature = f"*{personality['title']} of the Royal Court* {personality['emoji']}"
        if signature not in text and not text.endswith('---'):
            text = f"{text}\n\n{signature}\n\n---"
        return text.strip()
    
    # Split into lines for processing (avoid regex for line-by-line processing)
    lines = response_text.split('\n')
    formatted_lines = []
    in_code_block = False
    
    for line in lines:
        # Handle code blocks (simplified check)
        line_stripped = line.strip()
        if line_stripped.startswith('```'):
            formatted_lines.append(line_stripped)
            in_code_block = not in_code_block
            continue
        
        if in_code_block:
            # Preserve code exactly as is
            formatted_lines.append(line)
            continue
        
        # Process non-code lines
        if not line_stripped:
            formatted_lines.append('')
            continue
        
        # Handle special formatting (simplified)
        if line_stripped.startswith('###'):
            formatted_lines.extend(['', line_stripped, ''])
        elif (line_stripped.startswith('*"') and line_stripped.endswith('"*')) or \
             (line_stripped.startswith('"') and line_stripped.endswith('"')):
            if not line_stripped.startswith('*"'):
                line_stripped = f'*"{line_stripped[1:-1]}"*'
            formatted_lines.extend(['', line_stripped, ''])
        elif line_stripped.startswith(('-', '*', '1.', '2.', '3.', '4.', '5.')):
            formatted_lines.append(line_stripped)
        else:
            # Clean up punctuation spacing using pre-compiled patterns
            line_cleaned = REGEX_PATTERNS['space_before_punct'].sub(r'\1', line_stripped)
            line_cleaned = REGEX_PATTERNS['space_after_punct'].sub(r'\1 ', line_cleaned)
            line_cleaned = REGEX_PATTERNS['multiple_spaces'].sub(' ', line_cleaned)
            formatted_lines.append(line_cleaned)
    
    # Join and clean up
    formatted_text = '\n'.join(formatted_lines)
    formatted_text = REGEX_PATTERNS['excessive_newlines'].sub('\n\n', formatted_text)
    formatted_text = formatted_text.strip()
    
    # Ensure proper header and signature
    if not formatted_text.startswith('###'):
        formatted_text = f"### {personality['title']} Speaks {personality['emoji']}\n\n{formatted_text}"
    
    signature = f"*{personality['title']} of the Royal Court* {personality['emoji']}"
    if signature not in formatted_text and not formatted_text.endswith('---'):
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
