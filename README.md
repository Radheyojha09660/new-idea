# Video Streaming Website

A complete, production-ready video streaming website that fetches videos from Telegram channels/groups and serves them via a modern web interface.

## Features

- **Telegram Integration**: Fetches videos from configured Telegram channels/groups using Pyrogram
- **JSON Storage**: Permanent storage of video metadata in JSON format
- **HTML5 Streaming**: Direct streaming in browser without redirects
- **Admin Panel**: Password-protected dashboard for managing videos
- **Search Functionality**: Search videos by title, size, or duration
- **Resume Playback**: Saves and resumes video position using localStorage
- **Responsive Design**: Mobile-friendly UI with modern card layout
- **Background Sync**: Automatic periodic syncing of new videos
- **Thumbnail Caching**: Local caching of video thumbnails

## Project Structure

```
/project
├── app.py                 # Main FastAPI application
├── telegram_client.py     # Telegram API integration
├── sync_worker.py         # Background video syncing
├── config.py              # Configuration and environment variables
├── video_cache.json       # JSON database for video metadata
├── templates/
│   ├── index.html         # Home page
│   ├── watch.html         # Video player page
│   └── admin.html         # Admin panel
├── static/
│   ├── css/
│   │   └── style.css      # Stylesheet
│   ├── js/
│   │   ├── script.js      # Home page scripts
│   │   ├── watch.js       # Video player scripts
│   │   └── admin.js       # Admin panel scripts
│   └── thumbnails/        # Cached thumbnails
├── requirements.txt       # Python dependencies
└── README.md              # This file
```

## How JSON Sync Works

The synchronization process is handled by `sync_worker.py`:

1. **Periodic Execution**: Runs every `SYNC_INTERVAL` seconds (default 1 hour)
2. **Fetch Videos**: Calls `telegram_client.py` to retrieve video messages from configured channels
3. **Metadata Extraction**: Extracts video details including ID, title, size, duration, etc.
4. **Deduplication**: Checks `video_cache.json` for existing videos using `unique_video_id`
5. **Storage**: Appends new videos to the JSON cache without overwriting existing data
6. **Thumbnail Caching**: Downloads and caches video thumbnails locally

The JSON structure stores videos as a dictionary with `unique_video_id` as keys, ensuring fast lookups and preventing duplicates.

## How Streaming Works

Video streaming is implemented via the `/stream/{file_id}` endpoint:

1. **Request Handling**: FastAPI receives request with Telegram file_id
2. **Download**: Uses Pyrogram to download the video file to a temporary location
3. **Streaming Response**: Returns a `StreamingResponse` that serves the file in chunks
4. **HTML5 Playback**: The `<video>` tag can directly play the streamed content
5. **Cleanup**: Temporary file is deleted after streaming completes

This approach provides direct streaming without exposing Telegram URLs or requiring video pre-downloading.

## Installation

1. Clone or download the project files
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

Set the following environment variables:

- `API_ID`: Your Telegram API ID
- `API_HASH`: Your Telegram API Hash
- `CHANNELS`: Comma-separated list of channel/group IDs (e.g., "@mychannel,@mygroup")
- `ADMIN_PASSWORD`: Password for admin panel access
- `SYNC_INTERVAL`: Sync interval in seconds (default: 3600)
- `PORT`: Server port (default: 10000)

## Usage

1. Set environment variables
2. Run the application:
   ```bash
   python app.py
   ```
3. Access the website at `http://localhost:10000`
4. Admin panel at `http://localhost:10000/admin`

## Deployment

### Local Development
```bash
python app.py
```

### Production (Render/Railway/VPS)
- Ensure `host = "0.0.0.0"` and `port = int(os.environ.get("PORT", 10000))`
- Install dependencies from `requirements.txt`
- Start with `uvicorn app:app --host 0.0.0.0 --port $PORT`

### Docker (Optional)
```dockerfile
FROM python:3.9
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "10000"]
```

## Security Notes

- Store API credentials securely as environment variables
- Use strong admin password
- The app includes basic rate limiting via FastAPI
- No hardcoded secrets in the code

## Limitations

- Videos are streamed on-demand; large libraries may require caching optimization
- Telegram API rate limits apply
- Thumbnails are cached locally; monitor disk space

## License

This project is provided as-is for educational and personal use.