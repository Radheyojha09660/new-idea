# Fallback: Show Telegram videos from cache if sync fails
@app.get("/telegram-videos", response_class=HTMLResponse)
async def telegram_videos_page(request: Request):
    try:
        with open("video_cache.json", "r") as f:
            videos = list(json.load(f).values())
    except Exception:
        videos = []
    return templates.TemplateResponse("index.html", {
        "request": request,
        "folder_hierarchy": {},
        "videos": videos,
        "current_user": None
    })
# Move Telegram video to another folder/category
from fastapi import Body

@app.post("/api/telegram/move_video")
async def move_telegram_video(
    video_id: str = Form(...),
    new_folder: str = Form(...),
    auth_token: str = Cookie(None)
):
    """Move a Telegram video to another folder/category."""
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        from auth import verify_token, load_users
        username = verify_token(auth_token)
        users = load_users()
        if username not in users:
            raise HTTPException(status_code=401, detail="User not found")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid authentication")

    db = load_db()
    video = db.get(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    # Only allow moving Telegram videos
    if video.get('source_type') != 'telegram':
        raise HTTPException(status_code=400, detail="Only Telegram videos can be moved with this endpoint")
    # Update folder/category
    video['folder_name'] = new_folder
    video['folder_path'] = new_folder
    save_db(db)
    return {"message": f"Video moved to {new_folder}"}
from fastapi import FastAPI, Request, HTTPException, Form, BackgroundTasks, File, UploadFile, Response, Cookie
from fastapi.responses import StreamingResponse
from starlette.responses import RedirectResponse
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import yt_dlp
import json
import os
from datetime import datetime
import aiofiles
import shutil
from auth import get_current_user, authenticate_user, register_user
import asyncio
try:
    from telegram_client import fetch_videos_from_channel
    from telegram_client import get_client
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
import tempfile
# --- TELEGRAM VIDEO STREAM ENDPOINT ---
@app.get("/api/telegram/stream/{file_id}")
async def stream_telegram_video(file_id: str):
    """Stream Telegram video by file_id (no download, direct stream)"""
    if not TELEGRAM_AVAILABLE:
        raise HTTPException(status_code=400, detail="Telegram client not available")
    client = await get_client()
    # Use a temp file for streaming
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        temp_path = tmp.name
    try:
        await client.download_media(file_id, file_name=temp_path)
        def iterfile():
            with open(temp_path, mode="rb") as file_like:
                yield from file_like
        return StreamingResponse(iterfile(), media_type="video/mp4")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Streaming failed: {e}")
    finally:
        try:
            os.remove(temp_path)
        except Exception:
            pass

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# Only mount videos directory if it exists
import os
if os.path.exists("videos"):
    app.mount("/videos", StaticFiles(directory="videos"), name="videos")

templates = Jinja2Templates(directory="templates")

VIDEO_DB = "video_db.json"
FOLDER_DB = "folder_db.json"

# Authentication routes
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None):
    return templates.TemplateResponse("login.html", {"request": request, "error": error})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    user = authenticate_user(username, password)
    if not user:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid username or password"
        })

    from auth import create_access_token
    token = create_access_token({"sub": username})

    # Redirect admin users to admin panel, others to home
    redirect_url = "/admin" if user.get("role") == "admin" else "/"
    response = RedirectResponse(redirect_url, status_code=302)
    response.set_cookie(key="auth_token", value=token, httponly=True, max_age=6*30*24*60*60)
    return response

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, error: str = None, success: str = None):
    return templates.TemplateResponse("register.html", {
        "request": request,
        "error": error,
        "success": success
    })

@app.post("/register")
async def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...)
):
    if password != confirm_password:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Passwords do not match"
        })

    try:
        user = register_user(username, email, password)
        return templates.TemplateResponse("register.html", {
            "request": request,
            "success": "Account created successfully! You can now login."
        })
    except HTTPException as e:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": e.detail
        })

@app.post("/logout")
async def logout(response: Response):
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("auth_token")
    return response

def load_db():
    try:
        with open(VIDEO_DB, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_db(db):
    with open(VIDEO_DB, 'w') as f:
        json.dump(db, f, indent=2)

def load_folder_db():
    try:
        with open(FOLDER_DB, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_folder_db(db):
    with open(FOLDER_DB, 'w') as f:
        json.dump(db, f, indent=2)

def build_folder_hierarchy():
    """Build hierarchical folder structure from videos and folders"""
    db = load_db()
    folder_db = load_folder_db()

    # Get all unique folder paths
    folders = {}
    for video in db.values():
        folder_path = video.get('folder_path', video.get('folder_name', ''))
        if folder_path:
            folders[folder_path] = folders.get(folder_path, 0) + 1

    # Add folders from folder_db
    for folder_name, folder_info in folder_db.items():
        if folder_name not in folders:
            folders[folder_name] = 0

    # Build hierarchy
    hierarchy = {}
    for folder_path, count in folders.items():
        parts = folder_path.split('/')
        current = hierarchy
        for part in parts:
            if part not in current:
                current[part] = {'count': 0, 'subfolders': {}}
            current = current[part]['subfolders']
        # Set count on the deepest level
        if parts:
            current = hierarchy
            for part in parts[:-1]:
                current = current[part]['subfolders']
            current[parts[-1]]['count'] = count

    return hierarchy

def build_user_folder_hierarchy(username):
    """Build folder hierarchy for a specific user"""
    db = load_db()
    folder_db = load_folder_db()

    # Get user's folder paths
    folders = {}
    for video in db.values():
        if video.get('user_id') == username:
            folder_path = video.get('folder_path', video.get('folder_name', ''))
            if folder_path:
                folders[folder_path] = folders.get(folder_path, 0) + 1

    # Add user's folders from folder_db
    for folder_name, folder_info in folder_db.items():
        if folder_info.get('user_id') == username:
            if folder_name not in folders:
                folders[folder_name] = 0

    # Build hierarchy
    hierarchy = {}
    for folder_path, count in folders.items():
        parts = folder_path.split('/')
        current = hierarchy
        for part in parts:
            if part not in current:
                current[part] = {'count': 0, 'subfolders': {}}
            current = current[part]['subfolders']
        # Set count on the deepest level
        if parts:
            current = hierarchy
            for part in parts[:-1]:
                current = current[part]['subfolders']
            current[parts[-1]]['count'] = count

    return hierarchy


# Homepage route (public landing page)
@app.get("/welcome", response_class=HTMLResponse)
async def homepage(request: Request):
    return templates.TemplateResponse("homepage.html", {"request": request})

# Main app route (redirects to homepage if not logged in)
@app.get("/", response_class=HTMLResponse)
async def home(request: Request, auth_token: str = Cookie(None)):
    if not auth_token:
        return RedirectResponse("/welcome", status_code=302)
    try:
        from auth import verify_token
        username = verify_token(auth_token)
        if not username:
            return RedirectResponse("/login", status_code=302)
        from auth import load_users
        users = load_users()
        if username not in users:
            return RedirectResponse("/login", status_code=302)
        user = users[username]
    except Exception:
        return RedirectResponse("/login", status_code=302)
    db = load_db()
    user_videos = [video for video in db.values() if video.get('user_id') == user['username']]
    user_videos.sort(key=lambda x: x.get('added_time', ''), reverse=True)
    folder_hierarchy = build_user_folder_hierarchy(user['username'])
    return templates.TemplateResponse("index.html", {
        "request": request,
        "folder_hierarchy": folder_hierarchy,
        "videos": user_videos,
        "current_user": user
    })

@app.get("/folder/{folder_path:path}", response_class=HTMLResponse)
async def folder_page(request: Request, folder_path: str, auth_token: str = Cookie(None)):
    # Check authentication
    if not auth_token:
        return RedirectResponse("/login", status_code=302)

    try:
        from auth import verify_token, load_users
        username = verify_token(auth_token)
        users = load_users()
        if username not in users:
            return RedirectResponse("/login", status_code=302)
        user = users[username]
    except Exception:
        return RedirectResponse("/login", status_code=302)

    db = load_db()
    folder_db = load_folder_db()

    # Find user's videos in this folder and subfolders
    videos = []
    for video in db.values():
        if video.get('user_id') == username:
            video_folder = video.get('folder_path', video.get('folder_name', ''))
            if video_folder == folder_path or video_folder.startswith(folder_path + '/'):
                videos.append(video)

    # Get user's subfolders
    subfolders = {}
    for folder_name, folder_info in folder_db.items():
        if (folder_info.get('user_id') == username and
            folder_name.startswith(folder_path + '/') and
            folder_name.count('/') == folder_path.count('/') + 1):
            subfolder_name = folder_name.split('/')[-1]
            subfolders[subfolder_name] = folder_name

    return templates.TemplateResponse("folder.html", {
        "request": request,
        "folder_path": folder_path,
        "folder_name": folder_path.split('/')[-1],
        "videos": videos,
        "subfolders": subfolders,
        "current_user": user
    })

@app.get("/watch/{video_id}", response_class=HTMLResponse)
async def watch(request: Request, video_id: str, auth_token: str = Cookie(None)):
    # Check authentication
    if not auth_token:
        return RedirectResponse("/login", status_code=302)

    try:
        from auth import verify_token, load_users
        username = verify_token(auth_token)
        users = load_users()
        if username not in users:
            return RedirectResponse("/login", status_code=302)
        user = users[username]
    except Exception:
        return RedirectResponse("/login", status_code=302)

    db = load_db()
    video = db.get(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Check if video belongs to user
    if video.get('user_id') != username:
        raise HTTPException(status_code=403, detail="Access denied")

    # Increment views
    video['views_count'] = video.get('views_count', 0) + 1
    save_db(db)
    return templates.TemplateResponse("watch.html", {"request": request, "video": video, "current_user": user})

@app.post("/add_video")
async def add_video(
    background_tasks: BackgroundTasks,
    url: str = Form(...),
    folder_path: str = Form(None),
    new_folder: str = Form(None),
    auth_token: str = Cookie(None)
):
    # Verify user authentication
    if not auth_token:
        return {"error": "Authentication required"}, 401

    try:
        from auth import verify_token, load_users
        username = verify_token(auth_token)
        users = load_users()
        if username not in users:
            return {"error": "User not found"}, 401
        user = users[username]
    except Exception:
        return {"error": "Invalid authentication"}, 401

    # Use new_folder if provided, otherwise use folder_path
    actual_folder = new_folder if new_folder else folder_path
    if not actual_folder:
        return {"error": "Folder path is required"}, 400

    background_tasks.add_task(process_video, url, actual_folder, username)
    return {"message": "Video processing started"}

@app.get("/api/folders")
async def get_folders(auth_token: str = Cookie(None)):
    # Check authentication
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        from auth import verify_token, load_users
        username = verify_token(auth_token)
        users = load_users()
        if username not in users:
            raise HTTPException(status_code=401, detail="User not found")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid authentication")

    folder_hierarchy = build_user_folder_hierarchy(username)

    # Flatten hierarchy for backward compatibility
    def flatten_hierarchy(hierarchy, prefix=""):
        folders = []
        for name, data in hierarchy.items():
            full_path = f"{prefix}/{name}" if prefix else name
            folders.append({
                'name': full_path,
                'display_name': name,
                'count': data['count'],
                'path': full_path,
                'has_subfolders': bool(data['subfolders'])
            })
            # Recursively add subfolders
            folders.extend(flatten_hierarchy(data['subfolders'], full_path))
        return folders

    folders = flatten_hierarchy(folder_hierarchy)
    return {"folders": folders}

@app.get("/api/stream/{video_id}")
async def get_stream(video_id: str, auth_token: str = Cookie(None)):
    """Get streaming URL for a video"""
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        from auth import verify_token, load_users
        username = verify_token(auth_token)
        users = load_users()
        if username not in users:
            raise HTTPException(status_code=401, detail="User not found")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid authentication")

    db = load_db()
    video = db.get(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Check if video belongs to user
    if video.get('user_id') != username:
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        # Extract stream URL using yt-dlp
        url = video['source_url']
        
        # Try to get direct MP4/WebM URL
        ydl_opts = {
            'format': '18',  # 18 is MP4 format on YouTube
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 30,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                stream_url = info.get('url')
                
                if stream_url:
                    return {
                        "stream_url": stream_url,
                        "title": info.get('title', video.get('title')),
                        "duration": info.get('duration', 0),
                        "format": "mp4"
                    }
        except:
            pass
        
        # Fallback - try best format
        ydl_opts2 = {
            'format': 'best',
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts2) as ydl:
            info = ydl.extract_info(url, download=False)
            stream_url = info.get('url')
            
            if stream_url:
                return {
                    "stream_url": stream_url,
                    "title": info.get('title', video.get('title')),
                    "duration": info.get('duration', 0),
                    "format": "unknown"
                }
        
        # If we still don't have URL, use fallback embed
        return {
            "stream_url": None,
            "fallback_embed": f"https://www.youtube.com/embed/{video_id}?autoplay=1&controls=1&rel=0",
            "error": "Could not extract direct stream",
            "title": video.get('title')
        }
        
    except Exception as e:
        print(f"Error extracting stream: {e}")
        # Return fallback with embed URL
        return {
            "stream_url": None,
            "fallback_embed": f"https://www.youtube.com/embed/{video_id}?autoplay=1&controls=1&rel=0",
            "error": str(e),
            "title": video.get('title')
        }


@app.post("/api/rename_folder")
async def rename_folder(old_name: str = Form(...), new_name: str = Form(...), auth_token: str = Cookie(None)):
    """Rename a folder and update all videos in it"""
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        from auth import verify_token, load_users
        username = verify_token(auth_token)
        users = load_users()
        if username not in users:
            raise HTTPException(status_code=401, detail="User not found")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid authentication")

    db = load_db()
    folder_db = load_folder_db()

    # Update all user's videos with the old folder name
    for video in db.values():
        if video.get('user_id') == username and video.get('folder_name') == old_name:
            video['folder_name'] = new_name

    # Update folder in folder_db if it belongs to user
    if old_name in folder_db and folder_db[old_name].get('user_id') == username:
        folder_info = folder_db[old_name]
        folder_info['name'] = new_name
        folder_info['path'] = new_name
        folder_db[new_name] = folder_info
        del folder_db[old_name]
        save_folder_db(folder_db)

    # Rename physical folder
    old_path = os.path.join("videos", username, old_name)
    new_path = os.path.join("videos", username, new_name)

    if os.path.exists(old_path):
        os.rename(old_path, new_path)

    save_db(db)
    return {"message": f"Folder renamed from {old_name} to {new_name}"}



@app.get("/api/telegram/channels")
async def get_telegram_channels():
    """Get list of configured Telegram channels"""
    if not TELEGRAM_AVAILABLE:
        return {"error": "Telegram client not available", "channels": []}
    
    import config
    channels = config.CHANNELS or []
    return {"channels": channels}

@app.get("/api/telegram/sync/{channel}")
async def sync_telegram_channel(channel: str, background_tasks: BackgroundTasks):
    """Sync videos from a Telegram channel"""
    if not TELEGRAM_AVAILABLE:
        raise HTTPException(status_code=400, detail="Telegram client not available")
    
    try:
        # Queue background task
        background_tasks.add_task(fetch_and_store_telegram_videos, channel)
        return {"message": f"Syncing channel: {channel}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/telegram/videos")
async def get_telegram_videos():
    """Get all Telegram videos from cache"""
    try:
        import config
        cache_file = config.VIDEO_CACHE_FILE
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                return json.load(f)
    except:
        pass
    return {}

async def fetch_and_store_telegram_videos(channel: str):
    """Background task to fetch and store Telegram videos"""
    if not TELEGRAM_AVAILABLE:
        return
    
    try:
        videos = await fetch_videos_from_channel(channel)
        db = load_db()
        
        for video in videos:
            unique_id = video.get('unique_video_id')
            if unique_id and unique_id not in db:
                # Use file_id for streaming
                file_id = video.get('file_id') or video.get('stream_url') or ''
                db[unique_id] = {
                    'video_id': unique_id,
                    'title': video.get('title', 'Telegram Video'),
                    'source_url': f"/api/telegram/stream/{file_id}",
                    'folder_name': f"📱 {video.get('channel_name', 'Telegram')}",
                    'embed_url': f"/watch/{unique_id}",
                    'thumbnail_path': video.get('thumbnail_path', ''),
                    'duration': video.get('duration', 0),
                    'file_size': video.get('file_size', 0),
                    'added_time': datetime.now().isoformat(),
                    'views_count': 0,
                    'source_type': 'telegram',
                    'file_id': file_id,
                    'message_id': video.get('message_id'),
                    'channel_id': video.get('channel_id')
                }
        
        save_db(db)
        print(f"Synced {len(videos)} videos from {channel}")
    except Exception as e:
        print(f"Error syncing Telegram channel: {e}")

async def process_video(url: str, folder_name: str, username: str = None):
    try:
        import re

        # Check if it's a playlist URL
        playlist_id = None
        playlist_patterns = [
            r'youtube\.com/playlist\?list=([a-zA-Z0-9_-]+)',
            r'youtube\.com/watch\?.*list=([a-zA-Z0-9_-]+)',
        ]
        for pattern in playlist_patterns:
            match = re.search(pattern, url)
            if match:
                playlist_id = match.group(1)
                break

        if playlist_id:
            # Process playlist
            await process_playlist(playlist_id, folder_name, username)
            return

        # Extract single video_id from URL - YouTube IDs are exactly 11 alphanumeric/dash characters
        patterns = [
            r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
            r'youtu\.be/([a-zA-Z0-9_-]{11})',
            r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
            r'youtube\.com/live/([a-zA-Z0-9_-]{11})',
            r'youtube\.com/watch\?v=([a-zA-Z0-9_-]+)',  # Allow longer IDs as fallback
            r'youtu\.be/([a-zA-Z0-9_-]+)',  # Allow longer IDs as fallback
        ]

        video_id = None
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                extracted_id = match.group(1)
                # Validate: YouTube video IDs should be 11 characters
                if len(extracted_id) == 11:
                    video_id = extracted_id
                    break
                # If not 11 chars, it might be a live video or playlist - try anyway
                elif len(extracted_id) > 0:
                    video_id = extracted_id
                    break

        if not video_id:
            print(f"Invalid YouTube URL: {url}")
            return
        
        # Clean video_id - ensure no special characters except dash and underscore
        video_id = video_id.strip()

        # Check if exists
        db = load_db()
        if video_id in db:
            print("Video already exists")
            return

        # Create folder if it doesn't exist
        if username:
            folder_path = os.path.join("videos", username, folder_name)
        else:
            folder_path = os.path.join("videos", folder_name)
        os.makedirs(folder_path, exist_ok=True)

        # Save folder to folder_db if it doesn't exist
        folder_db = load_folder_db()
        if folder_name not in folder_db:
            folder_db[folder_name] = {
                'name': folder_name.split('/')[-1],
                'path': folder_name,
                'parent_path': '/'.join(folder_name.split('/')[:-1]) if '/' in folder_name else '',
                'user_id': username,
                'created_time': datetime.now().isoformat()
            }
            save_folder_db(folder_db)

        # Use embed URL for YouTube
        embed_url = f"https://www.youtube.com/embed/{video_id}"

        # Use basic info (yt-dlp causing issues)
        title = f"YouTube Video {video_id}"
        duration = 0
        thumbnail_url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"

        # Download thumbnail
        thumbnail_path = os.path.join("static", "thumbnails", f"{video_id}.jpg")
        os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)
        try:
            import urllib.request
            urllib.request.urlretrieve(thumbnail_url, thumbnail_path)
        except:
            # Create a placeholder
            with open(thumbnail_path, 'wb') as f:
                f.write(b'')  # Empty file

        # Save to db
        db[video_id] = {
            'video_id': video_id,
            'user_id': username,  # Associate with user
            'title': title,
            'source_url': url,
            'folder_path': folder_name,  # Changed from folder_name to folder_path
            'folder_name': folder_name.split('/')[-1],  # Keep for backward compatibility
            'embed_url': embed_url,
            'thumbnail_path': thumbnail_path,
            'duration': duration,
            'file_size': 0,  # Not downloaded
            'added_time': datetime.now().isoformat(),
            'views_count': 0
        }
        save_db(db)
        print(f"Video added: {title}")
    except Exception as e:
        print(f"Error processing video: {e}")

async def process_playlist(playlist_id: str, folder_name: str, username: str = None):
    try:
        # Use yt-dlp to extract playlist info
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,  # Don't download, just get metadata
            'socket_timeout': 30,
        }

        playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(playlist_url, download=False)

        if 'entries' not in info:
            print(f"No entries found in playlist {playlist_id}")
            return

        db = load_db()
        added_count = 0

        for entry in info['entries']:
            if not entry:
                continue

            video_id = entry.get('id')
            if not video_id or video_id in db:
                continue  # Skip if already exists

            # Create folder if it doesn't exist
            if username:
                folder_path = os.path.join("videos", username, folder_name)
            else:
                folder_path = os.path.join("videos", folder_name)
            os.makedirs(folder_path, exist_ok=True)

            # Save folder to folder_db if it doesn't exist
            folder_db = load_folder_db()
            if folder_name not in folder_db:
                folder_db[folder_name] = {
                    'name': folder_name.split('/')[-1],
                    'path': folder_name,
                    'parent_path': '/'.join(folder_name.split('/')[:-1]) if '/' in folder_name else '',
                    'user_id': username,
                    'created_time': datetime.now().isoformat()
                }
                save_folder_db(folder_db)

            # Use embed URL for YouTube
            embed_url = f"https://www.youtube.com/embed/{video_id}"

            # Get title from entry
            title = entry.get('title', f"YouTube Video {video_id}")
            duration = entry.get('duration', 0)
            thumbnail_url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"

            # Download thumbnail
            thumbnail_path = os.path.join("static", "thumbnails", f"{video_id}.jpg")
            os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)
            try:
                import urllib.request
                urllib.request.urlretrieve(thumbnail_url, thumbnail_path)
            except:
                # Create a placeholder
                with open(thumbnail_path, 'wb') as f:
                    f.write(b'')  # Empty file

            # Save to db
            db[video_id] = {
                'video_id': video_id,
                'user_id': username,
                'title': title,
                'source_url': f"https://www.youtube.com/watch?v={video_id}",
                'folder_path': folder_name,
                'folder_name': folder_name.split('/')[-1],
                'embed_url': embed_url,
                'thumbnail_path': thumbnail_path,
                'duration': duration,
                'file_size': 0,
                'added_time': datetime.now().isoformat(),
                'views_count': 0
            }

            added_count += 1
            print(f"Added playlist video: {title}")

        save_db(db)
        print(f"Playlist processing complete. Added {added_count} videos from playlist {playlist_id}")

    except Exception as e:
        print(f"Error processing playlist {playlist_id}: {e}")

@app.post("/api/delete_folder")
async def delete_folder(folder_name: str = Form(...), auth_token: str = Cookie(None)):
    """Delete a folder and all its videos from the database and filesystem"""
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        from auth import verify_token, load_users
        username = verify_token(auth_token)
        users = load_users()
        if username not in users:
            raise HTTPException(status_code=401, detail="User not found")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid authentication")

    db = load_db()
    folder_db = load_folder_db()

    # Remove all user's videos in the folder
    videos_to_delete = [video_id for video_id, video in db.items()
                       if video.get('user_id') == username and video.get('folder_name') == folder_name]

    for video_id in videos_to_delete:
        del db[video_id]

    # Remove folder from folder_db if it belongs to user
    if folder_name in folder_db and folder_db[folder_name].get('user_id') == username:
        del folder_db[folder_name]
        save_folder_db(folder_db)

    save_db(db)

    # Delete physical folder if it exists and is empty
    folder_path = os.path.join("videos", username, folder_name)
    try:
        if os.path.exists(folder_path):
            # Check if folder is empty or only contains .gitkeep or similar
            if not os.listdir(folder_path):
                os.rmdir(folder_path)
            else:
                # If not empty, still remove it (videos folder should be managed by database)
                import shutil
                shutil.rmtree(folder_path)
    except Exception as e:
        print(f"Warning: Could not delete physical folder {folder_path}: {e}")

    return {"message": f"Folder '{folder_name}' and all its videos deleted successfully"}

# Admin routes
@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request, auth_token: str = Cookie(None)):
    # Check if user is authenticated and is admin
    if not auth_token:
        return RedirectResponse("/login", status_code=302)

    try:
        from auth import verify_token
        username = verify_token(auth_token)
        if not username:
            return RedirectResponse("/login", status_code=302)

        from auth import load_users
        users = load_users()
        if username not in users:
            return RedirectResponse("/login", status_code=302)

        user = users[username]
        if user.get("role") != "admin":
            return RedirectResponse("/", status_code=302)  # Not admin, redirect to home

    except Exception:
        return RedirectResponse("/login", status_code=302)

    return templates.TemplateResponse("admin.html", {"request": request, "current_user": user})

@app.get("/api/admin/stats")
async def get_admin_stats(auth_token: str = Cookie(None)):
    # Verify admin access
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        from auth import verify_token, load_users
        username = verify_token(auth_token)
        users = load_users()
        user = users.get(username)

        if not user or user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")

    except Exception:
        raise HTTPException(status_code=401, detail="Invalid authentication")

    # Calculate statistics
    all_users = load_users()
    db = load_db()

    total_users = len(all_users)
    active_users = sum(1 for u in all_users.values() if u.get("is_active", True))
    total_videos = len(db)
    total_views = sum(video.get("views_count", 0) for video in db.values())

    # Calculate storage used (rough estimate)
    storage_used = 0
    for video in db.values():
        thumbnail_path = video.get("thumbnail_path", "")
        if thumbnail_path and os.path.exists(thumbnail_path):
            try:
                storage_used += os.path.getsize(thumbnail_path)
            except:
                pass

    # Convert to MB
    storage_used_mb = round(storage_used / (1024 * 1024), 2)

    # Count folders
    folder_db = load_folder_db()
    total_folders = len(folder_db)

    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_videos": total_videos,
        "total_views": total_views,
        "storage_used": storage_used_mb,
        "total_folders": total_folders
    }

@app.get("/api/admin/users")
async def get_all_users(auth_token: str = Cookie(None)):
    # Verify admin access
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        from auth import verify_token, load_users
        username = verify_token(auth_token)
        users = load_users()
        user = users.get(username)

        if not user or user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")

    except Exception:
        raise HTTPException(status_code=401, detail="Invalid authentication")

    # Return all users (exclude passwords)
    all_users = load_users()
    user_list = []
    for username, user_data in all_users.items():
        user_list.append({
            "username": username,
            "email": user_data.get("email"),
            "role": user_data.get("role", "user"),
            "is_active": user_data.get("is_active", True),
            "created_at": user_data.get("created_at"),
            "last_login": user_data.get("last_login"),
            "login_count": user_data.get("login_count", 0)
        })

    return {"users": user_list}

@app.post("/api/admin/users/{target_username}/toggle")
async def toggle_user_status(target_username: str, auth_token: str = Cookie(None)):
    # Verify admin access
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        from auth import verify_token, load_users, save_users
        username = verify_token(auth_token)
        users = load_users()
        user = users.get(username)

        if not user or user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")

        if target_username not in users:
            raise HTTPException(status_code=404, detail="User not found")

        if target_username == "admin":
            raise HTTPException(status_code=400, detail="Cannot modify admin user")

    except Exception:
        raise HTTPException(status_code=401, detail="Invalid authentication")

    # Toggle user status
    users[target_username]["is_active"] = not users[target_username].get("is_active", True)
    save_users(users)

    return {"message": f"User {target_username} status updated"}

@app.delete("/api/admin/users/{target_username}/delete")
async def delete_user(target_username: str, auth_token: str = Cookie(None)):
    # Verify admin access
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        from auth import verify_token, load_users, save_users
        username = verify_token(auth_token)
        users = load_users()
        user = users.get(username)

        if not user or user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")

        if target_username not in users:
            raise HTTPException(status_code=404, detail="User not found")

        if target_username == "admin":
            raise HTTPException(status_code=400, detail="Cannot delete admin user")

    except Exception:
        raise HTTPException(status_code=401, detail="Invalid authentication")

    # Delete user and all their data
    db = load_db()
    folder_db = load_folder_db()

    # Remove user's videos
    videos_to_delete = [vid for vid, video in db.items() if video.get("user_id") == target_username]
    for vid in videos_to_delete:
        del db[vid]

    # Remove user's folders
    folders_to_delete = [fid for fid, folder in folder_db.items() if folder.get("user_id") == target_username]
    for fid in folders_to_delete:
        del folder_db[fid]

    # Remove user account
    del users[target_username]

    # Save changes
    save_db(db)
    save_folder_db(folder_db)
    save_users(users)

    return {"message": f"User {target_username} and all their data deleted"}

@app.post("/api/create_subfolder")
async def create_subfolder(parent_path: str = Form(...), subfolder_name: str = Form(...), auth_token: str = Cookie(None)):
    """Create a new subfolder"""
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        from auth import verify_token, load_users
        username = verify_token(auth_token)
        users = load_users()
        if username not in users:
            raise HTTPException(status_code=401, detail="User not found")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid authentication")

    if not subfolder_name or not subfolder_name.strip():
        raise HTTPException(status_code=400, detail="Subfolder name is required")

    folder_db = load_folder_db()
    new_folder_path = f"{parent_path}/{subfolder_name.strip()}" if parent_path else subfolder_name.strip()

    if new_folder_path in folder_db:
        raise HTTPException(status_code=400, detail="Folder already exists")

    # Create physical folder
    folder_physical_path = os.path.join("videos", username, new_folder_path)
    os.makedirs(folder_physical_path, exist_ok=True)

    # Save to folder database
    folder_db[new_folder_path] = {
        'name': subfolder_name.strip(),
        'path': new_folder_path,
        'parent_path': parent_path,
        'user_id': username,
        'created_time': datetime.now().isoformat()
    }
    save_folder_db(folder_db)

    return {"message": f"Subfolder '{subfolder_name}' created successfully", "folder_path": new_folder_path}

@app.post("/api/move_video")
async def move_video(video_id: str = Form(...), new_folder_path: str = Form(...)):
    """Move a video to a different folder"""
    db = load_db()
    folder_db = load_folder_db()

    if video_id not in db:
        raise HTTPException(status_code=404, detail="Video not found")

    if new_folder_path and new_folder_path not in folder_db:
        raise HTTPException(status_code=400, detail="Target folder does not exist")

    video = db[video_id]
    old_folder = video.get('folder_path', video.get('folder_name', ''))

    # Update video folder
    video['folder_path'] = new_folder_path
    video['folder_name'] = new_folder_path.split('/')[-1] if new_folder_path else ''

    save_db(db)
    return {"message": f"Video moved from '{old_folder}' to '{new_folder_path}'"}

@app.post("/api/copy_video")
async def copy_video(video_id: str = Form(...), new_folder_path: str = Form(...)):
    """Copy a video to a different folder"""
    db = load_db()
    folder_db = load_folder_db()

    if video_id not in db:
        raise HTTPException(status_code=404, detail="Video not found")

    if new_folder_path and new_folder_path not in folder_db:
        raise HTTPException(status_code=400, detail="Target folder does not exist")

    video = db[video_id]
    new_video_id = f"{video_id}_copy_{int(datetime.now().timestamp())}"

    # Create copy of video
    new_video = video.copy()
    new_video['video_id'] = new_video_id
    new_video['folder_path'] = new_folder_path
    new_video['folder_name'] = new_folder_path.split('/')[-1] if new_folder_path else ''
    new_video['added_time'] = datetime.now().isoformat()
    new_video['views_count'] = 0

    db[new_video_id] = new_video
    save_db(db)

    return {"message": f"Video copied to '{new_folder_path}'", "new_video_id": new_video_id}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))