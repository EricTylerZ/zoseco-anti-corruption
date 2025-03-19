from flask import Flask, request, jsonify
import requests
import os
import json

app = Flask(__name__)

# Venice AI API configuration
VENICE_API_URL = "https://api.venice.ai/v1/chat/completions"
VENICE_API_KEY = os.environ.get("VENICE_API_KEY", "your-venice-api-key-here")

# File-based chat history storage
HISTORY_FILE = "/tmp/history.json"

def load_history():
    try:
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f)

@app.route("/query", methods=["POST"])
def handle_query():
    data = request.json
    user_query = data.get("query", "")
    chat_id = data.get("chat_id", None) or str(request.remote_addr)  # Use IP as fallback

    if not user_query:
        return jsonify({"error": "No query provided"}), 400

    # Load existing history
    chat_history = load_history()
    if chat_id not in chat_history:
        chat_history[chat_id] = []

    # Add user query to history
    chat_history[chat_id].append({"role": "user", "content": user_query})

    # Prepare Venice AI API request
    headers = {
        "Authorization": f"Bearer {VENICE_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "mixtral-8x7b",  # Adjust as needed
        "messages": [
            {"role": "system", "content": "You are an anti-corruption expert assisting users at zoseco.com. Be concise and helpful."},
            *chat_history[chat_id][-5:],  # Last 5 messages
        ],
        "max_tokens": 200,
        "temperature": 0.7
    }

    try:
        response = requests.post(VENICE_API_URL, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()

        ai_response = result["choices"][0]["message"]["content"].strip()
        chat_history[chat_id].append({"role": "assistant", "content": ai_response})

        # Save updated history
        save_history(chat_history)

        return jsonify({
            "response": ai_response,
            "chat_id": chat_id,
            "history": chat_history[chat_id]
        })

    except Exception as e:
        print(f"Error querying Venice AI: {e}")
        return jsonify({"error": "Failed to get response from AI"}), 500

@app.route("/history", methods=["GET"])
def get_history():
    chat_id = request.args.get("chat_id")
    chat_history = load_history()
    if chat_id in chat_history:
        return jsonify({"history": chat_history[chat_id]})
    return jsonify({"history": []})

if __name__ == "__main__":
    app.run()