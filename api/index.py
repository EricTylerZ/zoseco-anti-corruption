from flask import Flask, request, jsonify, Response, redirect, url_for, render_template_string
from flask_cors import CORS
from flask_dance.contrib.github import make_github_blueprint, github
from flask_dance.contrib.twitter import make_twitter_blueprint, twitter
from flask_dance.contrib.facebook import make_facebook_blueprint, facebook
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from datetime import datetime, timezone
from dotenv import load_dotenv
import requests
import os
import redis
import json
import logging
import uuid

# Load environment variables from .env file if present
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "your-secret-key-here")
CORS(app, resources={r"/api/*": {"origins": "https://zoseco.com"}})  # Restrict to your WordPress domain

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
PURITY_TEST_PROMPT = "You are an assistant for Zoseco's Purity Test. Be concise, friendly, and ask one question at a time to assess the user's trustworthiness."

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
    
    for model in models:
        model_id = model.get("id", "")
        if model_id == "mistral-31-24b":
            logger.info(f"Selected preferred model: {model_id}")
            return model_id
    
    for model in models:
        if "most_intelligent" in model.get("traits", []):
            model_id = model.get("id", "")
            logger.info(f"Selected most intelligent model: {model_id}")
            return model_id
    
    for model in models:
        if "default" in model.get("traits", []):
            model_id = model.get("id", "")
            logger.info(f"Selected default model: {model_id}")
            return model_id
    
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

# Flask-Login setup
login_manager = LoginManager(app)
login_manager.login_view = "index"

# OAuth blueprints
github_bp = make_github_blueprint(client_id=os.environ["GITHUB_CLIENT_ID"], client_secret=os.environ["GITHUB_CLIENT_SECRET"])
twitter_bp = make_twitter_blueprint(api_key=os.environ["TWITTER_API_KEY"], api_secret=os.environ["TWITTER_API_SECRET"])
facebook_bp = make_facebook_blueprint(client_id=os.environ["FACEBOOK_CLIENT_ID"], client_secret=os.environ["FACEBOOK_CLIENT_SECRET"])

app.register_blueprint(github_bp, url_prefix="/login")
app.register_blueprint(twitter_bp, url_prefix="/login")
app.register_blueprint(facebook_bp, url_prefix="/login")

# User model
class User(UserMixin):
    def __init__(self, id, provider):
        self.id = id
        self.provider = provider

@login_manager.user_loader
def load_user(user_id):
    provider = redis_client.get(f"user:{user_id}:provider") if redis_client else None
    if provider:
        return User(user_id, provider)
    return None

# Routes
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

# Authentication routes
@app.route("/api/check_auth")
def check_auth():
    if current_user.is_authenticated:
        return jsonify({"authenticated": True, "user": current_user.id, "provider": current_user.provider})
    return jsonify({"authenticated": False})

@app.route("/login/github")
def login_github():
    if not github.authorized:
        return redirect(url_for("github.login"))
    resp = github.get("/user")
    if resp.ok:
        user_id = resp.json()["login"]
        redis_client.set(f"user:{user_id}:provider", "github")
        login_user(User(user_id, "github"))
    return redirect("https://zoseco.com/purity-test")

@app.route("/login/twitter")
def login_twitter():
    if not twitter.authorized:
        return redirect(url_for("twitter.login"))
    resp = twitter.get("account/verify_credentials.json?include_email=true")
    if resp.ok:
        user_id = resp.json()["screen_name"]
        redis_client.set(f"user:{user_id}:provider", "twitter")
        login_user(User(user_id, "twitter"))
    return redirect("https://zoseco.com/purity-test")

@app.route("/login/facebook")
def login_facebook():
    if not facebook.authorized:
        return redirect(url_for("facebook.login"))
    resp = facebook.get("/me?fields=id,name")
    if resp.ok:
        user_id = resp.json()["name"]
        redis_client.set(f"user:{user_id}:provider", "facebook")
        login_user(User(user_id, "facebook"))
    return redirect("https://zoseco.com/purity-test")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("https://zoseco.com/purity-test")

# Purity Test chat routes
@app.route("/api/purity/start_chat", methods=["POST"])
def start_purity_chat():
    chat_id = str(uuid.uuid4())
    initial_message = {
        "content": "What do you think is happening in Valparaiso? Or is it always sunny here?",
        "role": "assistant",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ip": request.remote_addr,
        "model": MODEL,
        "tokens_out": 17
    }
    if current_user.is_authenticated:
        redis_client.set(f"user:{current_user.id}:purity_chat_id", chat_id)
        redis_client.set(f"purity_chat:{chat_id}", json.dumps([initial_message]))
    else:
        redis_client.setex(f"purity_chat:{chat_id}", 24 * 60 * 60, json.dumps([initial_message]))  # 24-hour expiration
    return jsonify({"chat_id": chat_id})

@app.route("/api/purity/history", methods=["GET"])
def get_purity_history():
    logger.info("Purity history route accessed")
    if not redis_client:
        return jsonify({"history": []})

    chat_id = request.args.get("chat_id")
    try:
        chat_history_json = redis_client.get(f"purity_chat:{chat_id}")
        chat_history = json.loads(chat_history_json) if chat_history_json else []
        return jsonify({"history": chat_history})
    except Exception as e:
        logger.error(f"Failed to get purity history: {e}")
        return jsonify({"history": []})

@app.route("/api/purity/query", methods=["POST"])
def handle_purity_query():
    logger.info("Purity query route accessed")
    data = request.json or {}
    user_query = data.get("query", "")
    chat_id = data.get("chat_id", str(request.remote_addr))

    if not user_query:
        return jsonify({"error": "No query provided"}), 400

    # Load history
    chat_history = []
    if redis_client:
        try:
            chat_history_json = redis_client.get(f"purity_chat:{chat_id}")
            chat_history = json.loads(chat_history_json) if chat_history_json else []
        except Exception as e:
            logger.error(f"Failed to load purity chat history: {e}")

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
            {"role": "system", "content": PURITY_TEST_PROMPT},
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
            if current_user.is_authenticated:
                redis_client.set(f"purity_chat:{chat_id}", json.dumps(chat_history))
                redis_client.set(f"user:{current_user.id}:purity_chat_id", chat_id)
            else:
                redis_client.setex(f"purity_chat:{chat_id}", 24 * 60 * 60, json.dumps(chat_history))
            logger.info(f"Saved purity chat history for chat_id: {chat_id}")
        except Exception as e:
            logger.error(f"Failed to save purity chat history: {e}")

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

# Standalone Purity Test page (optional)
@app.route("/purity-test")
def purity_test_page():
    return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Purity Test - Zoseco</title>
            <style>
                #auth-container { text-align: right; margin-bottom: 20px; }
                #chat-container { text-align: center; }
                #chat-container .subheader { text-align: left; max-width: 600px; margin: 0 auto; }
                #chat-window { max-height: 400px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; margin: 20px auto; background-color: #f9f9f9; max-width: 600px; border-radius: 5px; }
                .chat-input { display: flex; align-items: center; max-width: 600px; margin: 0 auto; }
                .message { margin-bottom: 10px; }
                .user-message { font-weight: bold; color: #00918B; }
                .assistant-message { color: #333; }
                .et_pb_button { display: inline-block; padding: 10px 20px; background-color: #00918B; color: #fff; text-decoration: none; border-radius: 5px; margin-left: 10px; }
                textarea { flex-grow: 1; padding: 8px; margin: 0 10px; border: 1px solid #ddd; }
                button { padding: 8px 16px; background-color: #00918B; color: #fff; border: none; cursor: pointer; }
            </style>
        </head>
        <body>
            <div id="auth-container">
                <div class="auth-buttons">
                    {% if not current_user.is_authenticated %}
                        <a href="/login/github" class="et_pb_button">Sign in with GitHub</a>
                        <a href="/login/twitter" class="et_pb_button">Sign in with X.com</a>
                        <a href="/login/facebook" class="et_pb_button">Sign in with Facebook</a>
                    {% else %}
                        <span>Welcome, {{ current_user.id }} ({{ current_user.provider }})!</span>
                        <a href="/logout" class="et_pb_button">Logout</a>
                    {% endif %}
                </div>
            </div>
            <div id="chat-container">
                <h1>Welcome to Zoseco</h1>
                <h2>How can we help you today?</h2>
                <p class="subheader">
                    If you are sharing tips but not logged in, your tips are initially considered far less trustworthy. 
                    Logged in Users will be able to see some other tips provided by others and help verify trustworthiness. 
                    The more trustworthy you prove to be, the more you will have access to. 
                    By using this tool you agree to our <a href="/terms">Terms here</a>. Please review before sending anything.
                </p>
                <div id="chat-window"></div>
                <div class="chat-input">
                    <input type="file" id="attachment" style="display: none;" />
                    <button id="attach-button">Upload File</button>
                    <textarea id="message-input" rows="4" placeholder="What do you think is happening in Valparaiso? Or is it always sunny here?"></textarea>
                    <button id="send-button">Send</button>
                </div>
            </div>
            <script>
                const SERVER_URL = "https://anti-corruption-bot-git-purity-test-erictylerzs-projects.vercel.app";
                let chatId = localStorage.getItem("purity_chat_id");

                // Check authentication status
                fetch(`${SERVER_URL}/api/check_auth`)
                    .then(response => response.json())
                    .then(data => {
                        const authContainer = document.getElementById("auth-container");
                        if (data.authenticated) {
                            authContainer.innerHTML = `
                                <span>Welcome, ${data.user} (${data.provider})!</span>
                                <a href="${SERVER_URL}/logout" class="et_pb_button">Logout</a>
                            `;
                        }
                    });

                // Start a new chat if no chat_id exists
                if (!chatId) {
                    fetch(`${SERVER_URL}/api/purity/start_chat`, { method: "POST" })
                        .then(response => response.json())
                        .then(data => {
                            chatId = data.chat_id;
                            localStorage.setItem("purity_chat_id", chatId);
                            loadHistory();
                        });
                } else {
                    loadHistory();
                }

                // Load chat history
                function loadHistory() {
                    fetch(`${SERVER_URL}/api/purity/history?chat_id=${chatId}`)
                        .then(response => response.json())
                        .then(data => {
                            const chatWindow = document.getElementById("chat-window");
                            chatWindow.innerHTML = "";
                            data.history.forEach(msg => displayMessage(msg.role, msg.content));
                        })
                        .catch(error => {
                            console.error("History fetch error:", error);
                            localStorage.removeItem("purity_chat_id");
                            window.location.reload();
                        });
                }

                // Send message
                document.getElementById("send-button").addEventListener("click", () => {
                    const messageInput = document.getElementById("message-input");
                    const message = messageInput.value.trim();
                    if (!message) return;
                    displayMessage("user", message);
                    fetch(`${SERVER_URL}/api/purity/query`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ chat_id: chatId, query: message })
                    })
                        .then(response => response.json())
                        .then(data => {
                            if (data.error) {
                                displayMessage("assistant", `Error: ${data.error}`);
                            } else {
                                displayMessage("assistant", data.response);
                            }
                        })
                        .catch(error => {
                            console.error("Query fetch error:", error);
                            displayMessage("assistant", `Error: ${error.message}`);
                        });
                    messageInput.value = "";
                });

                // Attachment button (placeholder)
                document.getElementById("attach-button").addEventListener("click", () => {
                    document.getElementById("attachment").click();
                });

                // Display message in chat window
                function displayMessage(role, content) {
                    const chatWindow = document.getElementById("chat-window");
                    const div = document.createElement("div");
                    div.className = `message ${role}-message`;
                    div.textContent = `${role === "user" ? "You" : "Assistant"}: ${content}`;
                    chatWindow.appendChild(div);
                    chatWindow.scrollTop = chatWindow.scrollHeight;
                }
            </script>
        </body>
        </html>
    """, current_user=current_user)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)