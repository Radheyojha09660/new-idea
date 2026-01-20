# VideoHub - YouTube-Style Video Library

A modern, animated video library application built with FastAPI and featuring a YouTube-like user interface.

## 🎯 Features

### ✨ Core Features
- **YouTube Video Integration**: Add YouTube videos via URL
- **Smart Folder Management**: 
  - Select from existing folders
  - Create new folders on-the-fly when adding videos
  - Automatic folder organization
- **Modern YouTube-Like Design**: Dark theme with red accent colors, smooth animations
- **Responsive Layout**: Works seamlessly on desktop, tablet, and mobile
- **Video Search**: Real-time search across all videos
- **View Counter**: Track how many times each video has been watched

### 🎨 UI/UX Features
- **Animated Header** with sticky navigation
- **Dynamic Sidebar** with folder navigation
- **Smooth Transitions**: All interactions include smooth CSS animations
- **Hover Effects**: Interactive cards with depth and scale animations
- **Modal Dialogs**: Clean popup for adding new videos
- **Gradient Backgrounds**: Modern design with gradient overlays
- **Glass-morphism Effects**: Backdrop blur on header for modern aesthetics

### 🔥 Animations
- Fade-in animations on page load
- Slide animations for sidebar
- Scale and transform effects on hover
- Staggered animations for card lists
- Smooth color transitions
- Ripple effects on button clicks
- Modal pop-in animations

## 📁 Project Structure

```
/
├── app.py                 # FastAPI application
├── requirements.txt       # Python dependencies
├── templates/
│   ├── index.html        # Home page with folder/video grid
│   ├── folder.html       # Folder view with videos
│   ├── watch.html        # Video player page
│   └── admin.html        # Admin page
├── static/
│   ├── css/
│   │   ├── youtube.css   # Main YouTube-style CSS
│   │   └── style.css     # Original styles (optional)
│   ├── js/
│   │   ├── animations.js # Animation and interactivity
│   │   ├── main.js       # Main JavaScript
│   │   └── admin.js      # Admin JavaScript
│   └── thumbnails/       # Video thumbnails cache
├── videos/               # Video folder storage
│   ├── Physics/          # Example folder
│   ├── Chemistry/        # Example folder
│   └── ...
└── study-portal/         # Alternative portal

```

## 🚀 Installation

### Prerequisites
- Python 3.8+
- pip package manager

### Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the application**:
   ```bash
   python app.py
   ```

3. **Access the application**:
   Open your browser and navigate to `http://localhost:10000`

## 📋 How to Use

### Adding a Video

1. Click the **"Add Video"** button in the header (+ icon)
2. Enter the YouTube video URL
3. **Either**:
   - Select an existing folder from the dropdown
   - **Or** type a new folder name in the "Create New Folder" field
4. Click **"Add Video"** button
5. The system will:
   - Extract video metadata
   - Download the thumbnail
   - Create the folder if it doesn't exist
   - Save the video to the database
   - Redirect you to view it

### Browsing Videos

- **Home Page**: Shows all latest videos and all folders
- **Folder View**: Click any folder to see videos within it
- **Search**: Use the search bar to find videos by title (real-time)
- **Watch Video**: Click any video card to watch it

### Keyboard Shortcuts
- `Ctrl+K` (Windows/Linux) or `Cmd+K` (Mac) - Focus search bar

## 🎨 Design Highlights

### Color Scheme
- **Primary**: Red (#ff0000) - YouTube signature color
- **Secondary**: Dark (#030303) - Background
- **Tertiary**: Darker (#212121) - Cards/Elements
- **Text**: White (#ffffff) and Gray (#aaaaaa)

### Key CSS Features
- **Grid Layouts**: Responsive video and folder grids
- **Animations**: 40+ keyframe animations for smooth interactions
- **Glassmorphism**: Modern blur effects on header
- **Hover States**: Interactive scale and shadow effects
- **Responsive Design**: Breakpoints at 768px and 480px

### Font & Typography
- Primary Font: Segoe UI, Tahoma, Geneva, Verdana, sans-serif
- Smooth text rendering and optimal line-height
- Icon support via Font Awesome 6.4.0

## 🔧 API Endpoints

### Get Folders
```
GET /api/folders
Response:
{
  "folders": [
    {"name": "Physics", "count": 5},
    {"name": "Chemistry", "count": 3}
  ]
}
```

### Add Video
```
POST /add_video
Body: 
- url: YouTube URL
- folder_name: Target folder name

Returns: {"message": "Video processing started"}
```

### View Video
```
GET /watch/{video_id}
```

### View Folder
```
GET /folder/{folder_name}
```

## 📦 Dependencies

```
fastapi          # Web framework
uvicorn[standard] # ASGI server
yt-dlp           # YouTube video extraction
aiofiles         # Async file operations
jinja2           # Template engine
python-multipart # Form data parsing
```

## 🎬 Video Processing

Videos are processed asynchronously:
1. **Extract Metadata**: Video ID from URL
2. **Download Thumbnail**: From YouTube CDN to `/static/thumbnails/`
3. **Embed URL**: Creates YouTube embed URL
4. **Database Entry**: Saves video metadata to `video_db.json`
5. **Folder Creation**: Automatically creates folder in `/videos/` if needed

## 🌟 Future Enhancements

- [ ] User authentication
- [ ] Playlist support
- [ ] Video ratings and comments
- [ ] Watch history
- [ ] Recommendations algorithm
- [ ] Dark/Light theme toggle
- [ ] Video download functionality
- [ ] Advanced filtering and sorting
- [ ] Social sharing features

## 📝 Browser Support

- Chrome/Chromium: Full support
- Firefox: Full support
- Safari: Full support
- Edge: Full support
- Mobile browsers: Full responsive support

## 🐛 Troubleshooting

### Videos not loading
- Ensure YouTube is accessible
- Check internet connection
- Verify video URL is correct

### Thumbnails not showing
- Check `/static/thumbnails/` directory permissions
- Ensure YouTube CDN is accessible
- Fallback placeholder will display if thumbnail fails

### Folder not created
- Ensure `/videos/` directory is writable
- Check disk space availability
- Verify folder name doesn't contain invalid characters

## 📄 License

This project is open source and available under the MIT License.

## 👨‍💻 Author

Built with ❤️ as a modern video library management system.

---

**Enjoy exploring your videos with VideoHub! 🎥**
