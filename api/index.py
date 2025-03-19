from flask import Flask, request, jsonify
import requests
import os
from vercel_kv import KV

app = Flask(__name__)

# Venice AI API configuration
VENICE_API_URL = "https://api.venice.ai/v1/chat/completions"
VENICE_API_KEY = os.environ.get("VENICE_API_KEY", "your-venice-api-key-here")

# Vercel KV setup
kv = KV()  # Uses Vercel KV environment variables automatically

@app.route("/query", methods=["POST"])
def handle_query():
    data = request.json
    user_query = data.get("query", "")
    chat_id = data.get("chat_id", None) or str(request.remote_addr)  # Use IP as fallback

    if not user_query:
        return jsonify({"error": "No query provided"}), 400

    # Load existing history from KV
    chat_history = kv.get(chat_id) or []
    chat_history.append({"role": "user", "content": user_query})

    # Prepare Venice AI API request
    headers = {
        "Authorization": f"Bearer {VENICE_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "mixtral-8x7b",
        "messages": [
            {"role": "system", "content": "You are an anti-corruption expert assisting users at zoseco.com. Be concise and helpful."},
            *chat_history[-5:],  # Last 5 messages
        ],
        "max_tokens": 200,
        "temperature": 0.7
    }

    try:
        response = requests.post(VENICE_API_URL, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()

        ai_response = result["choices"][0]["message"]["content"].strip()
        chat_history.append({"role": "assistant", "content": ai_response})

        # Save to KV with 24-hour expiration
        kv.set(chat_id, chat_history, ex=86400)

        return jsonify({
            "response": ai_response,
            "chat_id": chat_id,
            "history": chat_history
        })

    except Exception as e:
        print(f"Error querying Venice AI: {e}")
        return jsonify({"error": "Failed to get response from AI"}), 500

@app.route("/history", methods=["GET"])
def get_history():
    chat_id = request.args.get("chat_id")
    chat_history = kv.get(chat_id) or []
    return jsonify({"history": chat_history})

# Admin endpoint (protect with a secret in production)
@app.route("/all_chats", methods=["GET"])
def get_all_chats():
    secret = request.args.get("secret")
    if secret != os.environ.get("ADMIN_SECRET", "your-secret-here"):  # Add this env var in Vercel
        return jsonify({"error": "Unauthorized"}), 403
    
    # Get all keys (limited by Redis SCAN in practice; adjust for large datasets)
    keys = kv.keys("*") or []
    all_chats = {key: kv.get(key) for key in keys}
    return jsonify({"chats": all_chats})

if __name__ == "__main__":
    app.run()