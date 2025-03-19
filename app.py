## Backend (app.py)
from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit, join_room
from flask_cors import CORS
import requests
import os
import uuid
import datetime
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, cors_allowed_origins="*")
CORS(app)

# Simple in-memory storage (replace with database in production)
chat_history = {}
active_chats = {}

# LLM API configuration
LLM_API_URL = os.environ.get('LLM_API_URL', 'https://api.openai.com/v1/chat/completions')
LLM_API_KEY = os.environ.get('LLM_API_KEY', 'your-api-key-here')

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/widget.js')
def widget_js():
    return app.send_static_file('widget.js')

@app.route('/api/start_chat', methods=['POST'])
def start_chat():
    data = request.json
    chat_id = str(uuid.uuid4())
    user_info = {
        'name': data.get('name', 'Anonymous'),
        'email': data.get('email', ''),
        'started_at': datetime.datetime.now().isoformat()
    }
    
    chat_history[chat_id] = []
    active_chats[chat_id] = user_info
    
    # Notify admin dashboard
    socketio.emit('new_chat', {'chat_id': chat_id, 'user_info': user_info}, room='admin')
    
    return jsonify({'chat_id': chat_id})

@app.route('/api/chats', methods=['GET'])
def get_chats():
    return jsonify({
        'active': active_chats,
        'history': chat_history
    })

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")

@socketio.on('join')
def handle_join(data):
    chat_id = data.get('chat_id')
    user_type = data.get('user_type', 'visitor')
    
    if user_type == 'admin':
        join_room('admin')
        print(f"Admin joined: {request.sid}")
    
    if chat_id:
        join_room(chat_id)
        print(f"User joined chat {chat_id}: {request.sid}")
        
        # Send chat history to the user
        if chat_id in chat_history:
            emit('chat_history', {'messages': chat_history[chat_id]})

@socketio.on('message')
def handle_message(data):
    chat_id = data.get('chat_id')
    message = data.get('message')
    sender = data.get('sender', 'visitor')
    
    if not chat_id or not message:
        return
    
    timestamp = datetime.datetime.now().isoformat()
    message_data = {
        'text': message,
        'sender': sender,
        'timestamp': timestamp
    }
    
    # Save to history
    if chat_id not in chat_history:
        chat_history[chat_id] = []
    chat_history[chat_id].append(message_data)
    
    # Broadcast to room
    emit('message', message_data, room=chat_id)
    
    # Also send to admin room
    emit('message', {'chat_id': chat_id, **message_data}, room='admin')
    
    # If message is from visitor, get AI response
    if sender == 'visitor':
        ai_response = get_ai_response(chat_id, message)
        if ai_response:
            ai_message = {
                'text': ai_response,
                'sender': 'agent',
                'timestamp': datetime.datetime.now().isoformat()
            }
            chat_history[chat_id].append(ai_message)
            emit('message', ai_message, room=chat_id)
            emit('message', {'chat_id': chat_id, **ai_message}, room='admin')

def get_ai_response(chat_id, message):
    """Get response from LLM API"""
    try:
        # Prepare context from chat history
        context = []
        if chat_id in chat_history:
            for msg in chat_history[chat_id][-10:]:  # Last 10 messages for context
                role = "assistant" if msg['sender'] == 'agent' else "user"
                context.append({"role": role, "content": msg['text']})
        
        # If using OpenAI format
        headers = {
            "Authorization": f"Bearer {LLM_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "gpt-3.5-turbo",  # Adjust based on your API
            "messages": [
                {"role": "system", "content": "You are a helpful assistant for zoseco.com. Be concise and friendly."},
                *context,
                {"role": "user", "content": message}
            ],
            "max_tokens": 150
        }
        
        response = requests.post(LLM_API_URL, headers=headers, json=payload, timeout=10)
        result = response.json()
        
        # Handle different API response formats (OpenAI example shown)
        if 'choices' in result and len(result['choices']) > 0:
            return result['choices'][0]['message']['content'].strip()
        else:
            return "I'm sorry, I couldn't process that request."
            
    except Exception as e:
        print(f"Error getting AI response: {e}")
        return "Sorry, I'm having trouble connecting to my brain right now."

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)