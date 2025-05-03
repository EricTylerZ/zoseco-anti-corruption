from flask import Flask, request, jsonify, Response, session
from flask_cors import CORS
from flask_session import Session
from datetime import datetime, timezone
from dotenv import load_dotenv
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import os
import redis
import json
import logging

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
# Allow CORS for WordPress and Vercel domains
CORS(app, supports_credentials=True, origins=[
    "https://zoseco.com",
    "https://anti-corruption-bot-git-anti-corrup-4c4c17-erictylerzs-projects.vercel.app",
    "https://anti-corruption-bot.vercel.app"
])

# Session configuration
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_REDIS'] = redis.Redis.from_url(os.environ.get("REDIS_URL", ""), decode_responses=True)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'default_secret_key')
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_SECURE'] = True
sess = Session(app)

# Venice AI API configuration
VENICE_API_URL = "https://api.venice.ai/api/v1/chat/completions"
VENICE_MODELS_URL = "https://api.venice.ai/api/v1/models"
VENICE_API_KEY = os.environ.get("VENICE_API_KEY", "")

# Redis configuration
REDIS_URL = os.environ.get("REDIS_URL")
redis_client = None
if REDIS_URL:
    try:
        redis_client = app.config['SESSION_REDIS']
        redis_client.ping()
        logger.info("Redis connected successfully")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
else:
    logger.warning("REDIS_URL not set, skipping Redis connection")

# System prompt
SYSTEM_PROMPT = os.environ.get("SYSTEM_PROMPT", "You are an anti-corruption expert. Be concise and helpful.")

# Model selection logic
def get_available_models():
    if not VENICE_API_KEY:
        logger.error("VENICE_API_KEY not set")
        return []
    headers = {
        "Authorization": f"Bearer {VENICE_API_KEY}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.get(VENICE_MODELS_URL, headers=headers, timeout=5)
        response.raise_for_status()
        models = response.json().get("data", [])
        logger.info(f"Fetched models: {models}")
        return models
    except requests.RequestException as e:
        logger.error(f"Failed to fetch models: {e}")
        return []

def select_best_model(models):
    if not models:
        logger.warning("No models available, using default")
        return "llama-3.3-70b"
    
    for model in models:
        model_id = model.get("id", "")
        if model_id == "mistral-31-24b":
            logger.info(f"Selected preferred model: {model_id}")
            return model_id
    
    for model in models:
        if "most_intelligent" in model.get("traits", []):
            model_id = model.get("   return model_id
    
    for model in models:
        if "default" in model.get("defau
Starting new chunk from line: 14373
    logger.warning("No preferred models found, using default")
    return "llama-3.3-70b"

def initialize_model():
    if redis_client:
        try:
            cached_models = redis_client.get("available_models")
            if cached_models:
                logger.info("Using cached models from Redis")
                return select_best_model(json.loads(cached_models))
        except Exception as e:
            logger.error(f"Redis cache fetch failed: {e}")
    
    models = get_available_models()
    selected_model = select_best_model(models)
    if redis_client and models:
        try:
            redis_client.setex("available_models", 86400, json.dumps(models))
            logger.info(f"Cached models for 24 hours: {models}")
        except Exception as e:
            logger.error(f"Redis cache set failed: {e}")
    return selected_model

MODEL = initialize_model()

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route("/", methods=["GET"])
def test_route():
    try:
        logger.info("Root route accessed")
        key_preview = VENICE_API_KEY[:4] + "..." if VENICE_API_KEY else "Not set"
        return jsonify({
            "message": "API is running",
            "redis_connected": bool(redis_client),
            "venice_api_key_preview": key_preview,
            "selected_model": MODEL
        })
    except Exception as e:
        logger.error(f"Error in test_route: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/api/register", methods=["POST"])
def register():
    try:
        data = request.json or {}
        username = data.get('username')
        password = data.get('password')
        if not username or not password:
            return jsonify({"error": "Username and password are required"}), 400
        if redis_client and redis_client.hget('users', username):
            return jsonify({"error": "User already exists"}), 400
        hashed_password = generate_password_hash(password)
        redis_client.hset('users', username, hashed_password)
        return jsonify({"message": "Registered successfully"}), 201
    except Exception as e:
        logger.error(f"Error in register: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/api/login", methods=["POST"])
def login():
    try:
        data = request.json or {}
        username = data.get('username')
        password = data.get('password')
        if not redis_client:
            return jsonify({"error": "Redis not connected"}), 500
        stored_hash = redis_client.hget('users', username)
        if stored_hash and check_password_hash(stored_hash.decode('utf-8') if isinstance(stored_hash, bytes) else stored_hash, password):
            session['username'] = username
            return jsonify({"message": "Logged in successfully"}), 200
        return jsonify({"error": "Invalid credentials"}), 401
    except Exception as e:
        logger.error(f"Error in login: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/api/logout", methods=["POST"])
def logout():
    try:
        session.pop('username', None)
        return jsonify({"message": "Logged out"}), 200
    except Exception as e:
        logger.error(f"Error in logout: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/api/check_login", methods=["GET"])
def check_login():
    try:
        if 'username' in session:
            return jsonify({"logged_in": True, "username": session['username']}), 200
        return jsonify({"logged_in": False}), 200
    except Exception as e:
        logger.error(f"Error in check_login: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/api/query", methods=["POST"])
@login_required
def handle_query():
    try:
        logger.info("Query route accessed")
        data = request.json or {}
        user_query = data.get("query", "")
        chat_id = session['username']

        if not user_query:
            return jsonify({"error": "No query provided"}), 400

        chat_history = []
        if redis_client:
            try:
                chat_history_json = redis_client.get(chat_id)
                chat_history = json.loads(chat_history_json) if chat_history_json else []
            except Exception as e:
                logger.error(f"Failed to load chat history: {e}")

        user_message = {
            "content": user_query,
            "role": "user",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ip": request.remote_addr,
            "model": MODEL,
            "tokens_in": len(user_query.split())
        }
        chat_history.append(user_message)

        headers = {
            "Authorization": f"Bearer {VENICE_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                *chat_history[-5:],
            ],
            "max_tokens": 177,
            "temperature": 0.7
        }

        response = requests.post(VENICE_API_URL, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()
        logger.info(f"Venice AI response: {result}")

        ai_response = result["choices"][0]["message"]["content"].strip()
        ai_message = {
            "content": ai_response,
            "role": "assistant",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ip": request.remote_addr,
            "model": MODEL,
            "tokens_out": len(ai_response.split()),
            "tokens_in": len(user_query.split())
        }
        chat_history.append(ai_message)

        if redis_client:
            try:
                redis_client.set(chat_id, json.dumps(chat_history))
                logger.info(f"Saved chat history for chat_id: {chat_id}")
            except Exception as e:
                logger.error(f"Failed to save chat history: {e}")

        return jsonify({
            "response": ai_response,
            "chat_id": chat_id,
            "history": chat_history
        })
    except requests.RequestException as e:
        logger.error(f"Venice AI request failed: {str(e)}")
        return jsonify({"error": f"Failed to get response from AI: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Unexpected error in handle_query: {str(e)}")
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500

@app.route("/api/history", methods=["GET"])
@login_required
def get_history():
    try:
        logger.info("History route accessed")
        if not redis_client:
            return jsonify({"history": []})

        chat_id = session['username']
        try:
            chat_history_json = redis_client.get(chat_id)
            chat_history = json.loads(chat_history_json) if chat_history_json else []
            return jsonify({"history": chat_history})
        except Exception as e:
            logger.error(f"Failed to get history: {e}")
            return jsonify({"history": []})
    except Exception as e:
        logger.error(f"Error in get_history: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/api/all_chats", methods=["GET"])
def get_all_chats():
    try:
        logger.info("All chats route accessed")
        if not redis_client:
            return jsonify({"chats": {}})

        secret = request.args.get("secret")
        if secret != os.environ.get("ADMIN_SECRET", "your-secret-here"):
            return jsonify({"error": "Unauthorized"}), 403

        keys = redis_client.keys("*")
        all_chats = {}
        for key in keys:
            chat_history_json = redis_client.get(key)
            if chat_history_json:
                chat_history = json.loads(chat_history_json)
                enriched_history = []
                for msg in chat_history:
                    if not isinstance(msg, dict):
                        continue
                    enriched_msg = {
                        "content": msg.get("content", ""),
                        "role": msg.get("role", ""),
                        "timestamp": msg.get("timestamp", datetime.now(timezone.utc).isoformat()),
                        "ip": msg.get("ip", "unknown"),
                        "model": msg.get("model", MODEL),
                        "tokens_in": msg.get("tokens_in", len(msg.get("content", "").split())),
                        "tokens_out": msg.get("tokens_out", len(msg.get("content", "").split())) if msg.get("role") == "assistant" else 0
                    }
                    enriched_history.append(enriched_msg)
                all_chats[key] = enriched_history

        if request.args.get("download") == "true":
            formatted_json = json.dumps({"chats": all_chats}, indent=2)
            return Response(
                formatted_json,
                mimetype="application/json",
                headers={"Content-Disposition": "attachment; filename=anti_corruption_chats.json"}
            )
        
        return jsonify({"chats": all_chats})
    except Exception as e:
        logger.error(f"Error in get_all_chats: {e}")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)