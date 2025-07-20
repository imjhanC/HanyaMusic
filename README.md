# My Own Spotify - Music Player

A modern music player built with Python and CustomTkinter that allows you to search and stream music from YouTube.

## Features

- 🔍 Search for music on YouTube
- 🎵 Stream audio directly from YouTube
- 🎛️ Modern UI with playback controls
- ⏯️ Play, pause, next, previous controls
- 📊 Real-time progress tracking
- 🖼️ Thumbnail display for videos
- 🎨 Spotify-inspired dark theme

## Installation

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Install VLC Media Player:**
   - Download and install VLC from [https://www.videolan.org/vlc/](https://www.videolan.org/vlc/)
   - Make sure VLC is in your system PATH

## Usage

1. **Run the application:**
   ```bash
   python main.py
   ```

2. **Search for music:**
   - Enter a song name, artist, or any search term
   - Click "Search" or press Enter
   - Browse through the results

3. **Play music:**
   - Click the play button (▶) on any result card
   - Or click on the song title
   - The bottom player bar will appear with controls

4. **Control playback:**
   - ⏮ Previous track
   - ▶/⏸ Play/Pause
   - ⏭ Next track
   - Drag the slider to seek through the song

## Features Explained

### Bottom Player Bar
When you click play on any music card, a bottom bar appears with:
- **Thumbnail**: Video thumbnail
- **Song Info**: Title and artist
- **Progress Bar**: Shows current position and total duration
- **Time Display**: Current time and total duration
- **Controls**: Previous, play/pause, next buttons

### Streaming
The app uses:
- **yt-dlp**: To extract audio stream URLs from YouTube
- **VLC**: To stream and play the audio
- **Fallback**: Simulated playback if VLC is not available

### UI Design
- **Dark Theme**: Spotify-inspired dark interface
- **Hover Effects**: Cards highlight on mouse hover
- **Responsive**: Adapts to window size
- **Modern Controls**: Clean, intuitive button design

## Troubleshooting

### VLC Not Found
If you get VLC-related errors:
1. Make sure VLC is installed and in your system PATH
2. The app will fall back to simulated playback if VLC is unavailable

### Audio Not Playing
1. Check your system volume
2. Ensure you have an internet connection
3. Some videos may have restrictions

### Search Not Working
1. Check your internet connection
2. YouTube may have rate limits
3. Try different search terms

## Dependencies

- **customtkinter**: Modern UI framework
- **youtube-search-python**: YouTube search functionality
- **yt-dlp**: YouTube video/audio extraction
- **python-vlc**: Audio streaming and playback
- **pygame**: Fallback audio support
- **Pillow**: Image processing for thumbnails
- **requests**: HTTP requests for thumbnails

## License

This project is for educational purposes. Please respect YouTube's terms of service. 