import vlc
import yt_dlp
import time

# YouTube URL
youtube_url = "https://www.youtube.com/watch?v=uXEUW792etk"

# Configure yt-dlp options
ydl_opts_highest_bitrate = {
    'format': 'bestaudio[abr>0]/bestaudio/best',
    'quiet': True,
    'no_warnings': True,
}

try:
    # Extract audio stream URL using yt-dlp
    with yt_dlp.YoutubeDL(ydl_opts_highest_bitrate) as ydl:
        info = ydl.extract_info(youtube_url, download=False)
        stream_url = info['url']
        print(f"Playing: {info.get('title', 'Unknown Title')}")
        
    # Initialize VLC instance
    vlc_instance = vlc.Instance('--intf', 'dummy')  # Use dummy interface
    player = vlc_instance.media_player_new()
    
    # Set media to the stream URL
    media = vlc_instance.media_new(stream_url)
    player.set_media(media)
    
    # Play the stream
    player.play()
    
    # Wait for media to start playing
    time.sleep(2)
    
    print("Playing audio... Press Ctrl+C to stop")
    
    # Keep the script running while playing
    while True:
        try:
            state = player.get_state()
            if state == vlc.State.Ended:
                print("Playback finished")
                break
            time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping playback...")
            player.stop()
            break
            
except Exception as e:
    print(f"Error: {e}")
    print("Make sure you have yt-dlp installed: pip install yt-dlp")