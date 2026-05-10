"""
keep_alive.py — Flask keep-alive server
Runs on port 8000 as a daemon thread so Replit never idles the project.
Import and call keep_alive() once at the top of bot.py.
"""
import threading
from flask import Flask, jsonify

_app = Flask(__name__)

@_app.route("/ping")
@_app.route("/ping/health")
def _ping():
    return jsonify({"status": "ok", "bot": "online"}), 200

def keep_alive():
    thread = threading.Thread(
        target=lambda: _app.run(host="0.0.0.0", port=8000, debug=False, use_reloader=False),
        daemon=True,
    )
    thread.start()
