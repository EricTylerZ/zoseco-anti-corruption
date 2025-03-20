from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from datetime import datetime, timezone
from dotenv import load_dotenv
import requests
import os
import redis
import json
import logging

# Load environment variables from .env file if present
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Venice AI API configuration
VENICE_API_URL = "https://api.venice.ai/api/v1/chat/completions"
VENICE_MODELS_URL = "https://api.venice.ai/api/v1/models"
VENICE_API_KEY = os.environ.get("VENICE_API_KEY", "your-venice-api-key-here")

# Upstash Redis configuration
REDIS_URL = os.environ.get("REDIS_URL")
redis_client = None
if REDIS_URL:
    try:
        redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        redis_client.ping()
        logger.info("Redis connected successfully")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
else:
    logger.warning("REDIS_URL not set, skipping Redis connection")

# System prompt from environment variable
SYSTEM_PROMPT = os.environ.get("SYSTEM_PROMPT", "You are an anti-corruption expert. Be concise and helpful.")

# Model selection logic
def get_available_models():
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
    
    # Prefer Mistral Small 3.1 24B
    for model in models:
        model_id = model.get("id", "")
        if model_id == "mistral-31-24b":
            logger.info(f"Selected preferred model: {model_id}")
            return model_id
    
    # Fallback to "most_intelligent" trait
    for model in models:
        if "most_intelligent" in model.get("traits", []):
            model_id = model.get("id", "")
            logger.info(f"Selected most intelligent model: {model_id}")
            return model_id
    
    # Fallback to "default" trait
    for model in models:
        if "default" in model.get("traits", []):
            model_id = model.get("id", "")
            logger.info(f"Selected default model: {model_id}")
            return model_id
    
    # Final fallback
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

@app.route("/", methods=["GET"])
def test_route():
    logger.info("Root route accessed")
    key_preview = VENICE_API_KEY[:4] + "..." if VENICE_API_KEY else "Not set"
    return jsonify({
        "message": "API is running",
        "redis_connected": bool(redis_client),
        "venice_api_key_preview": key_preview,
        "selected_model": MODEL
    })

@app.route("/api/query", methods=["POST"])
def handle_query():
    logger.info("Query route accessed")
    data = request.json or {}
    user_query = data.get("query", "")
    chat_id = data.get("chat_id", str(request.remote_addr))

    if not user_query:
        return jsonify({"error": "No query provided"}), 400

    # Load history
    chat_history = []
    if redis_client:
        try:
            chat_history_json = redis_client.get(chat_id)
            chat_history = json.loads(chat_history_json) if chat_history_json else []
        except Exception as e:
            logger.error(f"Failed to load chat history: {e}")

    # Add user message
    user_message = {
        "content": user_query,
        "role": "user",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ip": request.remote_addr,
        "model": MODEL,
        "tokens_in": len(user_query.split())
    }
    chat_history.append(user_message)

    # Venice AI API call
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

    try:
        logger.info(f"Sending request to Venice AI with key: {VENICE_API_KEY[:4]}... - Payload: {payload}")
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
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500

@app.route("/api/history", methods=["GET"])
def get_history():
    logger.info("History route accessed")
    if not redis_client:
        return jsonify({"history": []})

    chat_id = request.args.get("chat_id")
    try:
        chat_history_json = redis_client.get(chat_id)
        chat_history = json.loads(chat_history_json) if chat_history_json else []
        return jsonify({"history": chat_history})
    except Exception as e:
        logger.error(f"Failed to get history: {e}")
        return jsonify({"history": []})

@app.route("/api/all_chats", methods=["GET"])
def get_all_chats():
    logger.info("All chats route accessed")
    if not redis_client:
        return jsonify({"chats": {}})

    secret = request.args.get("secret")
    if secret != os.environ.get("ADMIN_SECRET", "your-secret-here"):
        return jsonify({"error": "Unauthorized"}), 403

    try:
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
        logger.error(f"Failed to get all chats: {e}")
        return jsonify({"chats": {}})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)