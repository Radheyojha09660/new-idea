import asyncio
import os
from pyrogram import Client
from pyrogram.types import Message
import config
import json
from datetime import datetime

client_lock = asyncio.Lock()
client_instance = None

async def get_client():
    global client_instance
    if client_instance is None:
        async with client_lock:
            if client_instance is None:
                if config.BOT_TOKEN:
                    # Use bot client
                    client_instance = Client(
                        "bot_session",
                        api_id=config.API_ID,
                        api_hash=config.API_HASH,
                        bot_token=config.BOT_TOKEN,
                        no_updates=True
                    )
                else:
                    # Use user client
                    client_instance = Client(
                        config.SESSION_FILE,
                        api_id=config.API_ID,
                        api_hash=config.API_HASH,
                        no_updates=True
                    )
                await client_instance.start()
    return client_instance

async def fetch_videos_from_channel(channel_id):
    client = await get_client()
    videos = []
    message_count = 0
    try:
        chat = await client.get_chat(channel_id)
        channel_name = chat.title
        print(f"Fetching from channel: {channel_name} ({channel_id})")
        # Try to join if not member
        try:
            await client.join_chat(channel_id)
            print(f"Joined channel: {channel_name}")
        except Exception:
            print(f"Already member or cannot join: {channel_name}")
        async for message in client.get_chat_history(channel_id, limit=100):  # Limit to 100 messages
            message_count += 1
            if message.video:
                video = message.video
                unique_id = f"{channel_id}_{message.id}"
                try:
                    thumbnail_path = await download_thumbnail_if_needed(client, getattr(video, 'thumbnail', None), unique_id)
                except Exception:
                    thumbnail_path = None
                data = {
                    'unique_video_id': unique_id,
                    'message_id': message.id,
                    'channel_id': channel_id,
                    'channel_name': channel_name,
                    'title': message.caption or video.file_name or f"Video {message.id}",
                    'description': message.caption,
                    'stream_url': f"/stream/{video.file_id}",
                    'file_id': video.file_id,
                    'thumbnail_path': thumbnail_path,
                    'file_size': video.file_size,
                    'duration': video.duration,
                    'mime_type': video.mime_type,
                    'views_count': 0,
                    'category': '',
                    'added_time': message.date.timestamp(),
                    'last_updated': message.date.timestamp()
                }
                videos.append(data)
        print(f"Checked {message_count} messages, found {len(videos)} videos")
    except Exception as e:
        print(f"Error fetching from {channel_id}: {e}")
    # Don't stop global client
    return videos

async def download_thumbnail_if_needed(client, thumbnail, unique_id):
    if not thumbnail:
        return None
    save_path = os.path.join(config.THUMBNAILS_DIR, f"{unique_id}.jpg")
    if not os.path.exists(save_path):
        await client.download_media(thumbnail.file_id, file=save_path)
    return save_path

async def get_video_stream(client, file_id):
    # This will be used in app.py for streaming
    # But since client is per call, perhaps pass file_id and download on demand
    pass

# Function to get all videos from all channels
async def fetch_all_videos():
    all_videos = []
    for channel in config.CHANNELS:
        videos = await fetch_videos_from_channel(channel.strip())
        all_videos.extend(videos)
    return all_videos