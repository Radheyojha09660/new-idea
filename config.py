import os
import json
from typing import List

# Load config from file
def load_config():
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

config = load_config()

# Telegram API credentials
API_ID = int(os.environ.get("API_ID", config.get('telegram_api_id', "26704085")))
API_HASH = os.environ.get("API_HASH", config.get('telegram_api_hash', "f150646c78f09b4f88bef191a22539c0"))
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")  # Optional, for bot if needed

# Channels/Groups to monitor (comma-separated in env)
CHANNELS = os.environ.get("CHANNELS", "@Rk_Movie096").split(",") if os.environ.get("CHANNELS") else []

# Admin password for admin panel
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")

# Server config
HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 10000))

# Sync interval in seconds (how often to check for new videos)
SYNC_INTERVAL = int(os.environ.get("SYNC_INTERVAL", 3600))  # Default 1 hour

# JSON cache file
VIDEO_CACHE_FILE = "video_cache.json"

# Thumbnails directory
THUMBNAILS_DIR = "static/thumbnails"

# Session file for Telegram client
SESSION_FILE = "telegram_session"