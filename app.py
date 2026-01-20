from fastapi import FastAPI, Request, HTTPException, Form, BackgroundTasks, File, UploadFile
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

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/videos", StaticFiles(directory="videos"), name="videos")
templates = Jinja2Templates(directory="templates")

VIDEO_DB = "video_db.json"

def load_db():
    try:
        with open(VIDEO_DB, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_db(db):
    with open(VIDEO_DB, 'w') as f:
        json.dump(db, f, indent=2)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    db = load_db()
    folders = {}
    all_videos = []
    for video in db.values():
        folder = video['folder_name']
        folders[folder] = folders.get(folder, 0) + 1
        all_videos.append(video)
    # Sort videos by added time (newest first)
    all_videos.sort(key=lambda x: x.get('added_time', ''), reverse=True)
    return templates.TemplateResponse("index.html", {"request": request, "folders": folders, "videos": all_videos})

@app.get("/folder/{folder_name}", response_class=HTMLResponse)
async def folder_page(request: Request, folder_name: str):
    db = load_db()
    videos = [v for v in db.values() if v['folder_name'] == folder_name]
    return templates.TemplateResponse("folder.html", {"request": request, "folder_name": folder_name, "videos": videos})

@app.get("/watch/{video_id}", response_class=HTMLResponse)
async def watch(request: Request, video_id: str):
    db = load_db()
    video = db.get(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    # Increment views
    video['views_count'] = video.get('views_count', 0) + 1
    save_db(db)
    return templates.TemplateResponse("watch.html", {"request": request, "video": video})

@app.post("/add_video")
async def add_video(background_tasks: BackgroundTasks, url: str = Form(...), folder_name: str = Form(None), new_folder: str = Form(None)):
    # Use new_folder if provided, otherwise use folder_name
    actual_folder = new_folder if new_folder else folder_name
    if not actual_folder:
        return {"error": "Folder name is required"}, 400
    background_tasks.add_task(process_video, url, actual_folder)
    return {"message": "Video processing started"}

@app.get("/api/folders")
async def get_folders():
    db = load_db()
    folders = {}
    for video in db.values():
        folder = video['folder_name']
        if folder not in folders:
            folders[folder] = {'name': folder, 'count': 0}
        folders[folder]['count'] += 1
    return {"folders": list(folders.values())}

@app.get("/api/stream/{video_id}")
async def get_stream(video_id: str):
    """Get streaming URL for a video"""
    db = load_db()
    video = db.get(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
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
async def rename_folder(old_name: str = Form(...), new_name: str = Form(...)):
    """Rename a folder and update all videos in it"""
    db = load_db()
    
    # Update all videos with the old folder name
    for video in db.values():
        if video['folder_name'] == old_name:
            video['folder_name'] = new_name
    
    # Rename physical folder
    old_path = os.path.join("videos", old_name)
    new_path = os.path.join("videos", new_name)
    
    if os.path.exists(old_path):
        os.rename(old_path, new_path)
    
    save_db(db)
    return {"message": f"Folder renamed from {old_name} to {new_name}"}

async def process_video(url: str, folder_name: str):
    try:
        # Extract video_id from URL - YouTube IDs are exactly 11 alphanumeric/dash characters
        import re
        # Try different URL patterns
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
        folder_path = os.path.join("videos", folder_name)
        os.makedirs(folder_path, exist_ok=True)

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
            'title': title,
            'source_url': url,
            'folder_name': folder_name,
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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))