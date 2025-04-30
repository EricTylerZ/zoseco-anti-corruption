from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import redis
import json
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "a-simple-secret")

# Redis setup
REDIS_URL = os.environ.get("REDIS_URL")
redis_client = None
if REDIS_URL:
    try:
        redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        redis_client.ping()
        print("Redis connected successfully")
    except Exception as e:
        print(f"Redis connection failed: {e}")

# Helper function to check Redis
def check_redis():
    if redis_client is None:
        flash("Database error. Please try again later.")
        return False
    return True

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

class User(UserMixin):
    def __init__(self, username):
        self.id = username

@login_manager.user_loader
def load_user(username):
    if check_redis() and redis_client.exists(f"user:{username}"):
        return User(username)
    return None

# Routes
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if not check_redis():
        return redirect(url_for("home"))
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if redis_client.exists(f"user:{username}"):
            flash("Username taken!")
        else:
            hashed_password = generate_password_hash(password)
            redis_client.set(f"user:{username}", json.dumps({"password": hashed_password}))
            flash("Registered! Please log in.")
            return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if not check_redis():
        return redirect(url_for("home"))
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user_data = redis_client.get(f"user:{username}")
        if user_data and check_password_hash(json.loads(user_data)["password"], password):
            login_user(User(username))
            flash("Logged in!")
            return redirect(url_for("home"))
        flash("Wrong username or password.")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.")
    return redirect(url_for("home"))

@app.route("/submit", methods=["GET", "POST"])
def submit_tip():
    if not check_redis():
        return redirect(url_for("home"))
    if request.method == "POST":
        tip = request.form["tip"]
        user_id = current_user.id if current_user.is_authenticated else None
        tip_id = redis_client.incr("tip_counter")
        tip_data = {"content": tip, "user_id": user_id, "timestamp": datetime.now().isoformat()}
        redis_client.set(f"tip:{tip_id}", json.dumps(tip_data))
        if user_id:
            redis_client.rpush(f"user_tips:{user_id}", tip_id)
        flash("Tip submitted!")
        return redirect(url_for("home"))
    return render_template("submit.html")

@app.route("/my-tips")
@login_required
def my_tips():
    if not check_redis():
        return redirect(url_for("home"))
    tip_ids = redis_client.lrange(f"user_tips:{current_user.id}", 0, -1)
    tips = [json.loads(redis_client.get(f"tip:{tip_id}")) for tip_id in tip_ids if redis_client.get(f"tip:{tip_id}")]
    return render_template("my_tips.html", tips=tips)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)