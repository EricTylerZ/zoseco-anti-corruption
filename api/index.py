from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import requests
import os
import redis
import json
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Venice AI API configuration
VENICE_API_URL = "https://api.venice.ai/api/v1/chat/completions"
VENICE_API_KEY = os.environ.get("VENICE_API_KEY", "your-venice-api-key-here")

# Upstash Redis configuration
REDIS_URL = os.environ.get("REDIS_URL")
try:
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    redis_client.ping()
    logger.info("Redis connected successfully")
except Exception as e:
    logger.error(f"Redis connection failed: {e}")
    redis_client = None

# System prompt from environment variable
SYSTEM_PROMPT = os.environ.get("SYSTEM_PROMPT", "You are an anti-corruption expert. Be concise and helpful.")

# Model used
MODEL = "llama-3.1-405b"

@app.route("/", methods=["GET"])
def test_route():
    logger.info("Root route accessed")
    key_preview = VENICE_API_KEY[:4] + "..." if VENICE_API_KEY else "Not set"
    return jsonify({"message": "API is running", "redis_connected": bool(redis_client), "venice_api_key_preview": key_preview})

@app.route("/api/query", methods=["POST"])
def handle_query():
    logger.info("Query route accessed")
    if not redis_client:
        return jsonify({"error": "Redis not configured"}), 500

    data = request.json
    user_query = data.get("query", "")
    chat_id = data.get("chat_id", None) or str(request.remote_addr)

    if not user_query:
        return jsonify({"error": "No query provided"}), 400

    # Load history
    chat_history_json = redis_client.get(chat_id)
    chat_history = json.loads(chat_history_json) if chat_history_json else []

    # Add user message with metadata
    user_message = {
        "content": user_query,
        "role": "user",
        "timestamp": datetime.utcnow().isoformat(),
        "ip": request.remote_addr,
        "model": MODEL,
        "tokens_in": len(user_query.split())  # Rough estimate
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
        "max_tokens": 200,
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
            "timestamp": datetime.utcnow().isoformat(),
            "ip": request.remote_addr,
            "model": MODEL,
            "tokens_out": len(ai_response.split()),  # Rough estimate
            "tokens_in": len(user_query.split())  # From request
        }
        chat_history.append(ai_message)

        redis_client.setex(chat_id, 86400, json.dumps(chat_history))
        logger.info(f"Saved chat history for chat_id: {chat_id}")
        return jsonify({
            "response": ai_response,
            "chat_id": chat_id,
            "history": chat_history
        })
    except requests.exceptions.RequestException as e:
        logger.error(f"Venice AI request failed: {str(e)} - Response: {e.response.text if e.response else 'No response'}")
        return jsonify({"error": f"Failed to get response from AI: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500

@app.route("/api/history", methods=["GET"])
def get_history():
    logger.info("History route accessed")
    if not redis_client:
        return jsonify({"error": "Redis not configured"}), 500

    chat_id = request.args.get("chat_id")
    chat_history_json = redis_client.get(chat_id)
    chat_history = json.loads(chat_history_json) if chat_history_json else []
    return jsonify({"history": chat_history})

@app.route("/api/all_chats", methods=["GET"])
def get_all_chats():
    logger.info("All chats route accessed")
    if not redis_client:
        return jsonify({"error": "Redis not configured"}), 500

    secret = request.args.get("secret")
    if secret != os.environ.get("ADMIN_SECRET", "your-secret-here"):
        return jsonify({"error": "Unauthorized"}), 403

    keys = redis_client.keys("*")
    all_chats = {key: json.loads(redis_client.get(key)) for key in keys if redis_client.get(key)}

    # Check for download parameter
    if request.args.get("download") == "true":
        formatted_json = json.dumps({"chats": all_chats}, indent=2)
        return Response(
            formatted_json,
            mimetype="application/json",
            headers={"Content-Disposition": "attachment; filename=anti_corruption_chats.json"}
        )
    
    return jsonify({"chats": all_chats})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)