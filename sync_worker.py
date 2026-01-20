import json
import asyncio
import config
from telegram_client import fetch_all_videos

def load_cache():
    try:
        with open(config.VIDEO_CACHE_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_cache(cache):
    with open(config.VIDEO_CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)

async def sync_videos():
    cache = load_cache()
    new_videos = await fetch_all_videos()
    updated = False
    for video in new_videos:
        vid = video['unique_video_id']
        if vid not in cache:
            cache[vid] = video
            updated = True
    if updated:
        save_cache(cache)
        print(f"Synced {len(new_videos)} videos, total in cache: {len(cache)}")
    else:
        print("No new videos found.")

async def periodic_sync():
    while True:
        await sync_videos()
        await asyncio.sleep(config.SYNC_INTERVAL)