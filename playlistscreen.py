import customtkinter as ctk
from PIL import Image, ImageTk
import requests
from io import BytesIO
import threading
import yt_dlp
import re
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from FirebaseClass import FirebaseManager
import time
import asyncio
import aiohttp

class PlaylistScreen(ctk.CTkFrame):
    def __init__(self, parent, current_user, song_selection_callback, playlist_name="Saved Songs", back_callback=None, *args, **kwargs):
        print(f"[DEBUG] PlaylistScreen.__init__ called with playlist_name: {playlist_name}")
        super().__init__(parent, *args, **kwargs)
        self.current_user = current_user
        self.song_selection_callback = song_selection_callback
        self.playlist_name = playlist_name
        self.back_callback = back_callback
        self.firebase_manager = None
        self.configure(fg_color="transparent")
        
        print(f"[DEBUG] current_user: {current_user}")
        print(f"[DEBUG] firebase_manager: {self.firebase_manager}")
        
        # Track window resize state
        self._resize_in_progress = False
        self._resize_after_id = None
        
        # Song data cache with better structure
        self.song_data_cache = {}
        self.loading_songs = False
        
        # Optimized thread pool with more workers for faster parallel processing
        self.executor = ThreadPoolExecutor(max_workers=16, thread_name_prefix="song_loader")
        self.bind("<Destroy>", self._on_destroy)
        
        # Session for connection reuse
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        # Main container frame that fills the window
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Configure grid weights for main container
        self.main_container.grid_rowconfigure(1, weight=1)  # Content area
        self.main_container.grid_columnconfigure(0, weight=1)
        
        print("[DEBUG] Creating banner...")
        # Create banner at the top
        self.create_banner()
        
        print("[DEBUG] Creating content area...")
        # Create content area
        self.create_content_area()
        
        # Load songs based on playlist type
        if self.playlist_name == "Saved Songs":
            self.load_liked_songs()
        else:
            # For custom playlists, load from Firebase
            self.load_custom_playlist_songs()
        
        print("[DEBUG] PlaylistScreen.__init__ completed")

    def create_banner(self):
        """Create the banner with playlist name"""
        print("[DEBUG] create_banner called")
        # Banner container with solid color
        banner_container = ctk.CTkFrame(self.main_container, fg_color="#1DB954", height=200, corner_radius=15)
        banner_container.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        banner_container.grid_propagate(False)
        
        # Add back button
        back_button = ctk.CTkButton(
            banner_container,
            text="← Back",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#333333",
            hover_color="#555555",
            text_color="#FFFFFF",
            corner_radius=20,
            width=80,
            height=35,
            command=self.go_back
        )
        back_button.place(relx=0.05, rely=0.5, anchor="w")
        
        # Add playlist name overlay on banner
        self.playlist_name_label = ctk.CTkLabel(
            banner_container,
            text=self.playlist_name,
            font=ctk.CTkFont(size=32, weight="bold"),
            text_color="#FFFFFF"
        )
        self.playlist_name_label.place(relx=0.5, rely=0.5, anchor="center")
        print("[DEBUG] create_banner completed")

    def update_playlist_name(self, new_name):
        """Update the playlist name in the banner"""
        self.playlist_name = new_name
        if hasattr(self, 'playlist_name_label'):
            self.playlist_name_label.configure(text=new_name)
    
    def go_back(self):
        """Go back to the main screen"""
        if self.back_callback:
            self.back_callback()
        else:
            print("Back button clicked - returning to main screen")
            # For now, we'll just destroy this screen
            self.destroy()
    
    def create_content_area(self):
        """Create the content area for displaying songs"""
        print("[DEBUG] create_content_area called")
        # Create a frame to hold the canvas and scrollbar
        self.canvas_container = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.canvas_container.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.canvas_container.grid_rowconfigure(0, weight=1)
        self.canvas_container.grid_columnconfigure(0, weight=1)
        
        # Create canvas with scrollbar
        self.canvas = ctk.CTkCanvas(
            self.canvas_container,
            bg="#1a1a1a",
            highlightthickness=0
        )
        
        self.scrollbar = ctk.CTkScrollbar(
            self.canvas_container,
            orientation="vertical",
            command=self.canvas.yview
        )
        
        self.scrollable_frame = ctk.CTkFrame(
            self.canvas,
            fg_color="transparent"
        )
        
        # Configure the scrollable frame
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )
        
        # Pack the canvas and scrollbar
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        
        # Create window in canvas for the scrollable frame
        self.canvas_window = self.canvas.create_window(
            (0, 0),
            window=self.scrollable_frame,
            anchor="nw",
            tags=("scrollable_frame",)
        )
        
        # Configure canvas scrolling
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Mouse wheel binding for scrolling
        self._bind_mousewheel_events()
        
        # Bind events
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.bind("<Configure>", self._on_window_configure)
        
        # Initialize cards list
        self.cards = []
        print("[DEBUG] create_content_area completed")

    def _bind_mousewheel_events(self):
        """Bind mouse wheel events to multiple widgets for better coverage"""
        widgets_to_bind = [
            self.main_container, self, self.canvas, self.scrollable_frame
        ]
        
        for widget in widgets_to_bind:
            widget.bind("<MouseWheel>", self._on_mousewheel)
            widget.bind("<Button-4>", self._on_mousewheel)  # Linux scroll up
            widget.bind("<Button-5>", self._on_mousewheel)  # Linux scroll down
        
        # Make sure canvas can receive focus
        self.canvas.bind("<Button-1>", lambda e: self.canvas.focus_set())
    
    def extract_video_id(self, url):
        """Extract video ID from various YouTube URL formats - optimized"""
        # More efficient regex patterns in order of most common first
        patterns = [
            r'(?:youtu\.be/)([a-zA-Z0-9_-]{11})',  # Short URLs first (most common)
            r'(?:youtube\.com/watch\?v=)([a-zA-Z0-9_-]{11})',  # Standard watch URLs
            r'(?:youtube\.com/embed/)([a-zA-Z0-9_-]{11})',  # Embed URLs
            r'(?:youtube\.com/watch\?.*v=)([a-zA-Z0-9_-]{11})',  # URLs with other params
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def get_instant_song_data_fast(self, url):
        """OPTIMIZED: Get song data using fastest possible methods"""
        video_id = self.extract_video_id(url)
        if not video_id:
            return None
        
        # Check cache first
        if video_id in self.song_data_cache:
            cached_data = self.song_data_cache[video_id]
            if not cached_data.get('is_loading', False):
                return cached_data
        
        # Create basic structure immediately
        song_data = {
            'title': "Loading...",
            'thumbnail_url': f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
            'videoId': video_id,
            'uploader': "Loading...",
            'duration': "Loading...",
            'view_count': "Loading...",
            'url': url,
            'is_loading': True
        }
        
        return song_data
    
    def fetch_song_data_batch_parallel(self, urls, max_workers=20):
        """OPTIMIZED: Fetch song data for multiple URLs in parallel with improved duration/views extraction"""
        def fetch_single_fast(url):
            video_id = self.extract_video_id(url)
            if not video_id:
                return None
            
            # Check cache first
            if video_id in self.song_data_cache:
                cached = self.song_data_cache[video_id]
                if not cached.get('is_loading', False):
                    return cached
            
            song_data = {
                'title': "Loading...",
                'thumbnail_url': f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
                'videoId': video_id,
                'uploader': "Loading...",
                'duration': "Loading...",
                'view_count': "Loading...",
                'url': url,
                'is_loading': True
            }
            
            try:
                # Method 1: oEmbed API for title and uploader
                try:
                    oembed_url = f"https://www.youtube.com/oembed?url={url}&format=json"
                    response = self.session.get(oembed_url, timeout=2)
                    if response.status_code == 200:
                        data = response.json()
                        song_data['title'] = data.get('title', 'Unknown Title')[:100]
                        song_data['uploader'] = data.get('author_name', 'Unknown')[:50]
                        print(f"[DEBUG] Got oEmbed data for {video_id}: {song_data['title']}")
                except Exception as e:
                    print(f"[DEBUG] oEmbed failed for {video_id}: {e}")
                
                # Method 2: Enhanced YouTube page scraping with multiple patterns
                try:
                    page_response = self.session.get(
                        f"https://www.youtube.com/watch?v={video_id}", 
                        timeout=3,
                        headers={
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                        }
                    )
                    
                    if page_response.status_code == 200:
                        content = page_response.text
                        
                        # Try multiple patterns for duration extraction
                        duration_patterns = [
                            r'"lengthSeconds":"(\d+)"',
                            r'"approxDurationMs":"(\d+)"',
                            r'"duration":"(\d+)"',
                            r'"length_seconds":(\d+)',
                            r',"length":"(\d+)"'
                        ]
                        
                        duration_found = False
                        for pattern in duration_patterns:
                            duration_match = re.search(pattern, content)
                            if duration_match:
                                try:
                                    duration_value = int(duration_match.group(1))
                                    # Handle milliseconds vs seconds
                                    if duration_value > 100000:  # Likely milliseconds
                                        duration_value = duration_value // 1000
                                    if duration_value > 0:
                                        song_data['duration'] = self.format_duration(duration_value)
                                        duration_found = True
                                        print(f"[DEBUG] Found duration for {video_id}: {song_data['duration']} using pattern {pattern}")
                                        break
                                except ValueError:
                                    continue
                        
                        # Try multiple patterns for view count extraction
                        view_patterns = [
                            r'"viewCount":"(\d+)"',
                            r'"view_count":"(\d+)"',
                            r'"views":"(\d+)"',
                            r'"viewCountText":{"simpleText":"([\d,]+) views"',
                            r'"viewCountText":{"runs":\[{"text":"([\d,]+)"}'
                        ]
                        
                        view_found = False
                        for pattern in view_patterns:
                            view_match = re.search(pattern, content)
                            if view_match:
                                try:
                                    view_text = view_match.group(1).replace(',', '')
                                    view_count = int(view_text)
                                    if view_count > 0:
                                        song_data['view_count'] = self.format_views(view_count)
                                        view_found = True
                                        print(f"[DEBUG] Found views for {video_id}: {song_data['view_count']} using pattern {pattern}")
                                        break
                                except ValueError:
                                    continue
                        
                        print(f"[DEBUG] Page scraping for {video_id} - Duration: {duration_found}, Views: {view_found}")
                        
                except Exception as e:
                    print(f"[DEBUG] Page scraping failed for {video_id}: {e}")
                
                # Method 3: Try YouTube's internal API as fallback
                if song_data['duration'] == "Loading..." or song_data['view_count'] == "Loading...":
                    try:
                        api_url = f"https://www.youtube.com/youtubei/v1/player?key=AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
                        payload = {
                            "context": {
                                "client": {
                                    "clientName": "WEB",
                                    "clientVersion": "2.20231201.01.00"
                                }
                            },
                            "videoId": video_id
                        }
                        
                        api_response = self.session.post(
                            api_url,
                            json=payload,
                            timeout=2,
                            headers={'Content-Type': 'application/json'}
                        )
                        
                        if api_response.status_code == 200:
                            api_data = api_response.json()
                            video_details = api_data.get('videoDetails', {})
                            
                            if song_data['duration'] == "Loading...":
                                length_seconds = video_details.get('lengthSeconds')
                                if length_seconds:
                                    song_data['duration'] = self.format_duration(int(length_seconds))
                                    print(f"[DEBUG] Got duration from API for {video_id}: {song_data['duration']}")
                            
                            if song_data['view_count'] == "Loading...":
                                view_count = video_details.get('viewCount')
                                if view_count:
                                    song_data['view_count'] = self.format_views(int(view_count))
                                    print(f"[DEBUG] Got views from API for {video_id}: {song_data['view_count']}")
                    
                    except Exception as e:
                        print(f"[DEBUG] YouTube API failed for {video_id}: {e}")
                
                # Check if we have enough data to mark as not loading
                has_title = song_data['title'] != "Loading..."
                has_uploader = song_data['uploader'] != "Loading..."
                has_duration = song_data['duration'] != "Loading..."
                has_views = song_data['view_count'] != "Loading..."
                
                # Mark as complete if we have title and at least one other piece of data
                if has_title and (has_uploader or has_duration or has_views):
                    song_data['is_loading'] = False
                    self.song_data_cache[video_id] = song_data
                    print(f"[DEBUG] Fast load complete for {video_id} - Title: {has_title}, Duration: {has_duration}, Views: {has_views}")
                
                return song_data
                
            except Exception as e:
                print(f"[DEBUG] Error in fast fetch for {video_id}: {e}")
                song_data['is_loading'] = True
                return song_data
        
        # Process all URLs in parallel
        results = []
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="fast_fetch") as executor:
            # Submit all tasks
            future_to_url = {executor.submit(fetch_single_fast, url): url for url in urls}
            
            # Collect results as they complete
            for future in as_completed(future_to_url, timeout=20):
                try:
                    result = future.result(timeout=3)
                    if result:
                        results.append(result)
                except Exception as e:
                    print(f"[DEBUG] Future failed: {e}")
        
        return results
    
    def enhance_song_data_background(self, song_data_list):
        """OPTIMIZED: Background enhancement with better yt-dlp extraction for missing data"""
        def enhance_batch(batch):
            for song_data in batch:
                try:
                    video_id = song_data['videoId']
                    
                    # Skip if already fully loaded
                    needs_duration = song_data.get('duration') == "Loading..."
                    needs_views = song_data.get('view_count') == "Loading..."
                    needs_title = song_data.get('title') == "Loading..."
                    needs_uploader = song_data.get('uploader') == "Loading..."
                    
                    if not (needs_duration or needs_views or needs_title or needs_uploader):
                        continue
                    
                    print(f"[DEBUG] Background enhancing {video_id} with yt-dlp - needs duration: {needs_duration}, views: {needs_views}")
                    
                    # Use yt-dlp for comprehensive data extraction
                    ydl_opts = {
                        'quiet': True,
                        'no_warnings': True,
                        'extract_flat': False,
                        'skip_download': True,
                        'ignoreerrors': True,
                        'noplaylist': True,
                        'socket_timeout': 8,
                        'retries': 1,
                        'fragment_retries': 0,
                        'no_check_certificate': True,
                    }
                    
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(song_data['url'], download=False)
                        
                        if info:
                            # Update missing fields
                            if needs_title:
                                song_data['title'] = info.get('title', f'Video {video_id[:8]}')[:100]
                            
                            if needs_uploader:
                                song_data['uploader'] = info.get('uploader', info.get('channel', 'Unknown'))[:50]
                            
                            if needs_duration:
                                duration_seconds = info.get('duration')
                                if duration_seconds:
                                    song_data['duration'] = self.format_duration(duration_seconds)
                                    print(f"[DEBUG] yt-dlp extracted duration for {video_id}: {song_data['duration']}")
                                else:
                                    song_data['duration'] = "Live/Unknown"
                            
                            if needs_views:
                                view_count = info.get('view_count')
                                if view_count:
                                    song_data['view_count'] = self.format_views(view_count)
                                    print(f"[DEBUG] yt-dlp extracted views for {video_id}: {song_data['view_count']}")
                                else:
                                    song_data['view_count'] = "Views hidden"
                            
                            song_data['is_loading'] = False
                            self.song_data_cache[video_id] = song_data
                            
                            # Update UI immediately
                            self.after(0, lambda data=song_data: self.update_song_card(data))
                            
                        else:
                            # yt-dlp failed, set reasonable defaults
                            if needs_duration:
                                song_data['duration'] = "Unknown"
                            if needs_views:
                                song_data['view_count'] = "Views unavailable"
                            if needs_title:
                                song_data['title'] = f"Video {video_id[:8]}"
                            if needs_uploader:
                                song_data['uploader'] = "Unknown"
                            
                            song_data['is_loading'] = False
                            self.after(0, lambda data=song_data: self.update_song_card(data))
                
                except Exception as e:
                    print(f"[DEBUG] Background enhance failed for {song_data.get('videoId', 'unknown')}: {e}")
                    # Set fallback values
                    if song_data.get('duration') == "Loading...":
                        song_data['duration'] = "Unknown"
                    if song_data.get('view_count') == "Loading...":
                        song_data['view_count'] = "Views unavailable"
                    if song_data.get('title') == "Loading...":
                        song_data['title'] = f"Video {song_data.get('videoId', 'Unknown')[:8]}"
                    if song_data.get('uploader') == "Loading...":
                        song_data['uploader'] = "Unknown"
                    
                    song_data['is_loading'] = False
                    self.after(0, lambda data=song_data: self.update_song_card(data))
        
        # Filter songs that need enhancement
        songs_needing_enhancement = [
            song for song in song_data_list 
            if (song.get('duration') == "Loading..." or
                song.get('view_count') == "Loading..." or
                song.get('title') == "Loading..." or
                song.get('uploader') == "Loading...")
        ]
        
        if not songs_needing_enhancement:
            print("[DEBUG] No songs need background enhancement")
            return
        
        print(f"[DEBUG] Starting background enhancement for {len(songs_needing_enhancement)} songs")
        
        # Process in small batches to avoid overwhelming yt-dlp
        batch_size = 3
        
        def process_batches():
            for i in range(0, len(songs_needing_enhancement), batch_size):
                batch = songs_needing_enhancement[i:i + batch_size]
                enhance_batch(batch)
                # Small delay between batches to be nice to YouTube
                time.sleep(1.0)
        
        # Run in background thread
        threading.Thread(target=process_batches, daemon=True).start()
    
    def load_liked_songs(self):
        """OPTIMIZED: Load liked songs with ultra-fast display"""
        print(f"[DEBUG] load_liked_songs called")
        
        if not self.current_user:
            print("[DEBUG] User not logged in")
            self.show_empty_state("Please log in to view your liked songs")
            return
        
        print("[DEBUG] Showing loading state...")
        self.show_loading_state()
        
        def load_songs_ultra_fast():
            print("[DEBUG] load_songs_ultra_fast started")
            start_time = time.time()
            
            try:
                if self.firebase_manager is None:
                    try:
                        self.firebase_manager = FirebaseManager()
                    except Exception as e:
                        print(f"[DEBUG] Error initializing FirebaseManager: {e}")
                        self.after(0, lambda: self.show_error_state("Failed to initialize Firebase"))
                        return
                
                # Get liked URLs from Firebase
                liked_urls = self.firebase_manager.get_user_liked_songs(self.current_user)
                print(f"[DEBUG] Got {len(liked_urls) if liked_urls else 0} liked URLs")
                
                if not liked_urls:
                    self.after(0, lambda: self.show_empty_state("No liked songs yet"))
                    return
                
                # OPTIMIZED: Get data for all songs in parallel with higher worker count
                print(f"[DEBUG] Starting parallel fetch for {len(liked_urls)} songs...")
                fetch_start = time.time()
                
                instant_song_data = self.fetch_song_data_batch_parallel(liked_urls, max_workers=24)
                
                fetch_time = time.time() - fetch_start
                print(f"[DEBUG] Parallel fetch completed in {fetch_time:.2f}s, got {len(instant_song_data)} songs")
                
                # Display immediately
                display_start = time.time()
                self.after(0, lambda: self.display_songs(instant_song_data))
                display_time = time.time() - display_start
                
                total_time = time.time() - start_time
                print(f"[DEBUG] Total load time: {total_time:.2f}s (fetch: {fetch_time:.2f}s, display: {display_time:.2f}s)")
                
                # Start background enhancement for incomplete songs
                if instant_song_data:
                    self.enhance_song_data_background(instant_song_data)
                
            except Exception as e:
                print(f"[DEBUG] Error in load_songs_ultra_fast: {e}")
                import traceback
                traceback.print_exc()
                self.after(0, lambda: self.show_error_state("Failed to load liked songs"))
        
        # Start loading in background thread
        threading.Thread(target=load_songs_ultra_fast, daemon=True).start()

    def load_custom_playlist_songs(self):
        """OPTIMIZED: Load custom playlist songs with ultra-fast display"""
        print(f"[DEBUG] load_custom_playlist_songs called for playlist: {self.playlist_name}")
        
        if not self.current_user:
            print("[DEBUG] User not logged in")
            self.show_empty_state("Please log in to view your playlists")
            return
        
        print("[DEBUG] Showing loading state...")
        self.show_loading_state()
        
        def load_custom_songs_ultra_fast():
            print("[DEBUG] load_custom_songs_ultra_fast started")
            start_time = time.time()
            
            try:
                if self.firebase_manager is None:
                    try:
                        self.firebase_manager = FirebaseManager()
                    except Exception as e:
                        print(f"[DEBUG] Error initializing FirebaseManager: {e}")
                        self.after(0, lambda: self.show_error_state("Failed to initialize Firebase"))
                        return
                
                # Get playlist songs from Firebase
                playlist_songs = self.firebase_manager.get_playlist_songs(self.current_user, self.playlist_name)
                print(f"[DEBUG] Got {len(playlist_songs) if playlist_songs else 0} songs from Firebase")
                
                if not playlist_songs:
                    self.after(0, lambda: self.show_empty_state(f"Playlist '{self.playlist_name}' is empty"))
                    return
                
                # Extract URLs for parallel fetching
                urls = [song_obj['url'] for song_obj in playlist_songs if 'url' in song_obj]
                
                if not urls:
                    self.after(0, lambda: self.show_empty_state(f"No valid songs in playlist '{self.playlist_name}'"))
                    return
                
                # OPTIMIZED: Fetch all song data in parallel
                print(f"[DEBUG] Starting parallel fetch for {len(urls)} playlist songs...")
                fetch_start = time.time()
                
                instant_song_data = self.fetch_song_data_batch_parallel(urls, max_workers=24)
                
                fetch_time = time.time() - fetch_start
                print(f"[DEBUG] Parallel fetch completed in {fetch_time:.2f}s")
                
                # Merge any additional data from Firebase
                firebase_data_map = {song_obj['url']: song_obj for song_obj in playlist_songs}
                
                for song_data in instant_song_data:
                    firebase_song = firebase_data_map.get(song_data['url'], {})
                    
                    # Only override if Firebase has better data
                    if 'title' in firebase_song and firebase_song['title']:
                        song_data['title'] = firebase_song['title']
                    if 'uploader' in firebase_song and firebase_song['uploader']:
                        song_data['uploader'] = firebase_song['uploader']
                    if 'duration' in firebase_song and firebase_song['duration']:
                        song_data['duration'] = firebase_song['duration']
                    if 'added_at' in firebase_song:
                        song_data['added_at'] = firebase_song['added_at']
                
                total_time = time.time() - start_time
                print(f"[DEBUG] Custom playlist load time: {total_time:.2f}s")
                
                # Display immediately
                self.after(0, lambda: self.display_songs(instant_song_data))
                
                # Start background enhancement
                if instant_song_data:
                    self.enhance_song_data_background(instant_song_data)
                
            except Exception as e:
                print(f"[DEBUG] Error in load_custom_songs_ultra_fast: {e}")
                import traceback
                traceback.print_exc()
                self.after(0, lambda: self.show_error_state("Failed to load playlist songs"))
        
        # Start loading in background thread
        threading.Thread(target=load_custom_songs_ultra_fast, daemon=True).start()

    def update_song_card(self, song_data):
        """Update a specific song card with enhanced data"""
        video_id = song_data.get('videoId')
        if not video_id:
            return
        
        print(f"[DEBUG] Updating card for {video_id} with duration: {song_data.get('duration', 'N/A')}")
        
        # Find the card to update
        for card in self.cards:
            if hasattr(card, '_song_data') and card._song_data.get('videoId') == video_id:
                # Update the stored song data
                card._song_data = song_data
                
                # Update the title if it exists and has changed
                if hasattr(card, '_title') and card._title.winfo_exists():
                    current_title = card._title.cget("text")
                    if current_title != song_data['title'] and not song_data.get('is_loading', False):
                        card._title.configure(text=song_data['title'])
                
                # Update details label with improved logic
                if hasattr(card, '_details_label') and card._details_label.winfo_exists():
                    details = self.build_details_text(song_data)
                    card._details_label.configure(text=details)
                    print(f"[DEBUG] Updated details for {video_id}: {details}")
                else:
                    # Fallback: find details label manually
                    content_frame = None
                    for child in card.winfo_children():
                        if isinstance(child, ctk.CTkFrame) and child.cget("fg_color") == "transparent":
                            content_frame = child
                            break
                    
                    if content_frame:
                        # Find and update details label
                        for child in content_frame.winfo_children():
                            if isinstance(child, ctk.CTkLabel) and child.cget("text_color") == "gray":
                                details = self.build_details_text(song_data)
                                child.configure(text=details)
                                print(f"[DEBUG] Updated details text via fallback: {details}")
                                break
                break
    
    def build_details_text(self, song_data):
        """Build the details text for a song card - FIXED to always show available data"""
        details = []
        
        # Add uploader if available
        uploader = song_data.get('uploader')
        if uploader and uploader not in ["Loading...", "Unknown", "", None]:
            details.append(uploader)
        
        # Add duration if available - prioritize this
        duration = song_data.get('duration')
        if duration and duration not in ["Loading...", "", None]:
            if duration == "0:00":
                details.append("Live stream")
            else:
                details.append(duration)
        elif song_data.get('is_loading', False):
            details.append("Loading duration...")
        else:
            # Only show "Duration N/A" if we're not loading and truly don't have duration
            if duration == "Loading..." or duration in ["Unknown", "Live/Unknown"]:
                details.append("Duration unknown")
        
        # Add view count if available - ALWAYS INCLUDE IF WE HAVE IT
        view_count = song_data.get('view_count')
        if view_count and view_count not in ["Loading...", "", None]:
            if view_count == "0 views":
                details.append("No views")
            elif view_count in ["Views hidden", "Views unavailable"]:
                details.append("Views hidden")
            else:
                details.append(view_count)
        elif song_data.get('is_loading', False):
            details.append("Loading views...")
        else:
            # Show views status even if unavailable
            if view_count == "Loading..." or view_count in ["Views hidden", "Views unavailable"]:
                details.append("Views unavailable")
        
        if details:
            result = " • ".join(details)
            print(f"[DEBUG] Built details text: '{result}' for video {song_data.get('videoId', 'unknown')}")
            return result
        elif song_data.get('is_loading', False):
            return "Loading details..."
        else:
            return "Details unavailable"
    
    def format_duration(self, seconds):
        """Format duration in seconds to MM:SS or HH:MM:SS"""
        if not seconds or seconds <= 0:
            return "0:00"
        
        try:
            seconds = int(float(seconds))  # Handle string/float inputs
            minutes, secs = divmod(seconds, 60)
            hours, minutes = divmod(minutes, 60)
            
            if hours > 0:
                return f"{hours}:{minutes:02d}:{secs:02d}"
            else:
                return f"{minutes}:{secs:02d}"
        except (ValueError, TypeError):
            return "0:00"
    
    def format_views(self, view_count):
        """Format view count to readable format"""
        if not view_count or view_count <= 0:
            return "0 views"
        
        try:
            view_count = int(view_count)
            if view_count >= 1_000_000:
                return f"{view_count // 100000 / 10:.1f}M views"
            elif view_count >= 1_000:
                return f"{view_count // 100 / 10:.1f}K views"
            else:
                return f"{view_count} views"
        except (ValueError, TypeError):
            return "0 views"
    
    def show_loading_state(self):
        """Show loading state while fetching songs"""
        print("[DEBUG] show_loading_state called")
        # Clear existing content
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        
        # Create loading container
        loading_container = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
        loading_container.pack(expand=True, fill="both", pady=50)
        
        # Loading text
        loading_text = ctk.CTkLabel(
            loading_container,
            text=("Loading your liked songs..." if self.playlist_name == "Saved Songs"
                  else f"Loading '{self.playlist_name}'..."),
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#1DB954"
        )
        loading_text.pack(pady=20)
        
        # Loading spinner
        spinner_frame = ctk.CTkFrame(loading_container, fg_color="transparent", width=60, height=60)
        spinner_frame.pack(pady=10)
        spinner_frame.pack_propagate(False)
        
        spinner = ctk.CTkLabel(
            spinner_frame,
            text="⏳",
            font=ctk.CTkFont(size=40),
            text_color="#1DB954"
        )
        spinner.pack(expand=True)
        print("[DEBUG] show_loading_state completed")
        # Recalculate scroll region to possibly disable scrolling when loading view is small
        self.after_idle(self._update_scroll_region)
    
    def show_empty_state(self, message):
        """Show empty state when no songs are found"""
        print(f"[DEBUG] show_empty_state called with message: {message}")
        # Clear existing content
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        
        # Create empty state container
        empty_container = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
        empty_container.pack(expand=True, fill="both", pady=50)
        
        # Empty state icon
        empty_icon = ctk.CTkLabel(
            empty_container,
            text="♪",
            font=ctk.CTkFont(size=60),
            text_color="#666666"
        )
        empty_icon.pack(pady=20)
        
        # Empty state message
        empty_text = ctk.CTkLabel(
            empty_container,
            text=message,
            font=ctk.CTkFont(size=16),
            text_color="#888888"
        )
        empty_text.pack(pady=10)
        
        print("[DEBUG] show_empty_state completed")
        # Ensure scroll is disabled if content doesn't exceed canvas
        self.after_idle(self._update_scroll_region)

    def show_error_state(self, message):
        """Show error state when loading fails"""
        print(f"[DEBUG] show_error_state called with message: {message}")
        # Clear existing content
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        
        # Create error state container
        error_container = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
        error_container.pack(expand=True, fill="both", pady=50)
        
        # Error icon
        error_icon = ctk.CTkLabel(
            error_container,
            text="❌",
            font=ctk.CTkFont(size=60),
            text_color="#FF6B6B"
        )
        error_icon.pack(pady=20)
        
        # Error message
        error_text = ctk.CTkLabel(
            error_container,
            text=message,
            font=ctk.CTkFont(size=16),
            text_color="#FF6B6B"
        )
        error_text.pack(pady=10)
        
        print("[DEBUG] show_error_state completed")
        # Ensure scroll is disabled if error view doesn't exceed canvas
        self.after_idle(self._update_scroll_region)
    
    def display_songs(self, song_data_list):
        """Display the list of songs"""
        print(f"[DEBUG] display_songs called with {len(song_data_list)} songs")
        # Clear existing content
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        
        # Reset cards list
        self.cards = []
        
        # Configure grid for scrollable frame
        self.scrollable_frame.columnconfigure(0, weight=1)
        
        if not song_data_list:
            # Handle empty state
            self.show_empty_state("No songs found")
            return
        
        # Create song cards
        for idx, song_data in enumerate(song_data_list):
            self._add_song_card(song_data, idx)
        
        # Remove the last separator if it exists
        if len(song_data_list) > 0:
            last_separator_row = (len(song_data_list) - 1) * 2 + 1
            separators = self.scrollable_frame.grid_slaves(row=last_separator_row, column=0)
            for separator in separators:
                if isinstance(separator, ctk.CTkFrame) and separator.cget("height") == 1:
                    separator.destroy()
        
        # Update scroll region after all cards are added
        self.after_idle(self._update_scroll_region)
        print("[DEBUG] display_songs completed")

    def _add_song_card(self, song_data, idx):
        """Create a single song card with optimized image loading"""
        # Create main card frame with dynamic width
        card = ctk.CTkFrame(
            self.scrollable_frame,
            fg_color="#222222",
            corner_radius=10,
            height=100
        )
        
        # Store card reference and song data
        card._title = None
        card._details_label = None
        card._song_data = song_data
        
        # Bind mouse wheel events to the card
        self._bind_mousewheel_to_widget(card)
        
        # Configure grid for the card to take full width
        card.grid(row=idx*2, column=0, sticky="nsew", padx=15, pady=5)
        card.grid_columnconfigure(1, weight=1)
        card.grid_columnconfigure(2, weight=0, minsize=70)
        card.grid_columnconfigure(3, weight=0, minsize=50)
        
        # Thumbnail container with fixed aspect ratio
        thumb_container = ctk.CTkFrame(card, fg_color="transparent", width=120, height=80)
        thumb_container.grid(row=0, column=0, rowspan=2, padx=10, pady=10, sticky="nsw")
        thumb_container.grid_propagate(False)
        
        # Bind mouse wheel to thumbnail container
        self._bind_mousewheel_to_widget(thumb_container)
        
        # Thumbnail label
        thumb = ctk.CTkLabel(thumb_container, text="")
        thumb.pack(expand=True, fill="both")
        
        # Bind mouse wheel to thumbnail label
        self._bind_mousewheel_to_widget(thumb)
        
        # OPTIMIZED: Load thumbnail with connection reuse and caching
        self._load_thumbnail_optimized(thumb, song_data['thumbnail_url'])
        
        # Content frame that expands with window
        content_frame = ctk.CTkFrame(card, fg_color="transparent")
        content_frame.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(0, 20), pady=10)
        content_frame.columnconfigure(0, weight=1)
        
        # Bind mouse wheel to content frame
        self._bind_mousewheel_to_widget(content_frame)
        
        # Title with dynamic wrapping
        title_text = song_data['title']
        if song_data.get('is_loading', False) and title_text == "Loading...":
            title_text = f"Loading... (ID: {song_data.get('videoId', 'Unknown')[:8]})"
        
        title = ctk.CTkLabel(
            content_frame,
            text=title_text,
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
            justify="left",
            wraplength=0
        )
        title.grid(row=0, column=0, sticky="nsw", pady=(0, 5))
        
        # Bind mouse wheel to title label
        self._bind_mousewheel_to_widget(title)
        
        card._title = title
        
        # Build details text using the improved method
        details_text = self.build_details_text(song_data)
            
        details_label = ctk.CTkLabel(
            content_frame,
            text=details_text,
            font=ctk.CTkFont(size=14),
            text_color="gray",
            anchor="w",
            justify="left"
        )
        details_label.grid(row=1, column=0, sticky="nsw")
        
        # Bind mouse wheel to details label
        self._bind_mousewheel_to_widget(details_label)
        
        card._details_label = details_label
        
        # Unlike/Remove button (different behavior for Saved Songs vs custom playlists)
        if self.playlist_name == "Saved Songs":
            remove_button = ctk.CTkButton(
                card,
                text="♥",
                width=40,
                height=40,
                corner_radius=20,
                fg_color="#FF6B6B",
                hover_color="#FF5252",
                text_color="#FFFFFF",
                font=ctk.CTkFont(size=14),
                command=lambda: self._on_remove_from_playlist_clicked(song_data, remove_button)
            )
        else:
            remove_button = ctk.CTkButton(
                card,
                text="🗑",
                width=40,
                height=40,
                corner_radius=20,
                fg_color="#FF6B6B",
                hover_color="#FF5252",
                text_color="#FFFFFF",
                font=ctk.CTkFont(size=14),
                command=lambda: self._on_remove_from_playlist_clicked(song_data, remove_button)
            )

        remove_button.grid(row=0, column=2, rowspan=2, padx=(0, 10), pady=15, sticky="nsew")
        
        # Play button (right-aligned)
        play_btn = ctk.CTkButton(
            card,
            text="▶",
            width=60,
            height=40,
            corner_radius=20,
            fg_color="#1DB954",
            hover_color="#1ed760",
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=20, weight="bold"),
            border_width=0,
            border_spacing=0,
            command=lambda: self._on_song_selected(song_data)
        )
        play_btn.grid(row=0, column=3, rowspan=2, padx=(0, 15), pady=15, sticky="nsew")
        
        # Add a separator between items
        separator = ctk.CTkFrame(
            self.scrollable_frame,
            height=1,
            fg_color="#333333"
        )
        separator.grid(row=idx*2 + 1, column=0, sticky="ew", padx=20, pady=2)
        
        # Bind mouse wheel to separator too
        self._bind_mousewheel_to_widget(separator)
        
        self.cards.append(card)
        
        # Update wraplength on window resize
        def update_wraplength(event):
            available_width = max(100, card.winfo_width() - 270)
            title.configure(wraplength=available_width)
            
        card.bind('<Configure>', update_wraplength)

    def _bind_mousewheel_to_widget(self, widget):
        """Helper to bind mouse wheel events to a widget"""
        widget.bind("<MouseWheel>", self._on_mousewheel)
        widget.bind("<Button-4>", self._on_mousewheel)
        widget.bind("<Button-5>", self._on_mousewheel)

    def _load_thumbnail_optimized(self, thumb_label, thumbnail_url):
        """OPTIMIZED: Load thumbnail with session reuse and better error handling"""
        def load_image_async():
            try:
                # Use the shared session for connection reuse
                response = self.session.get(thumbnail_url, timeout=3, stream=True)
                response.raise_for_status()
                
                # Process image
                img = Image.open(BytesIO(response.content))
                img.thumbnail((120, 80), Image.Resampling.LANCZOS)
                tk_image = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                
                def update_image():
                    if thumb_label.winfo_exists():
                        thumb_label.configure(image=tk_image)
                        thumb_label.image = tk_image  # Keep reference
                
                self.after(0, update_image)
                
            except Exception as e:
                print(f"[DEBUG] Error loading thumbnail {thumbnail_url}: {e}")
                # Set a placeholder or default image
                def set_placeholder():
                    if thumb_label.winfo_exists():
                        thumb_label.configure(text="🎵", font=ctk.CTkFont(size=30))
                
                self.after(0, set_placeholder)
        
        # Submit to thread pool
        self.executor.submit(load_image_async)
    
    def _on_song_selected(self, song_data):
        """Called when a song is selected from the playlist"""
        if self.song_selection_callback:
            # Find the index of the selected song in the current results
            current_index = 0
            for i, card in enumerate(self.cards):
                if hasattr(card, '_song_data') and card._song_data.get('videoId') == song_data.get('videoId'):
                    current_index = i
                    break
            
            # Get all song data from cards
            all_songs = []
            for card in self.cards:
                if hasattr(card, '_song_data'):
                    all_songs.append(card._song_data)
            
            # Call the callback with song data, playlist, and current index
            self.song_selection_callback(song_data, all_songs, current_index)
    
    def _on_remove_from_playlist_clicked(self, song_data, remove_button):
        """Handle remove from playlist button click"""
        if not self.current_user or not self.firebase_manager:
            print("User not logged in")
            return
        
        video_id = song_data.get('videoId')
        if not video_id:
            print("No video ID found")
            return
        
        if self.playlist_name == "Saved Songs":
            # Remove from liked songs (uses unlike_song method)
            success = self.firebase_manager.unlike_song(self.current_user, video_id)
            if success:
                print(f"Removed '{song_data.get('title')}' from liked songs")
                self._remove_song_card(song_data)
            else:
                print(f"Failed to remove '{song_data.get('title')}' from liked songs")
        else:
            # Remove from custom playlist (uses remove_song_from_playlist method)
            success, message = self.firebase_manager.remove_song_from_playlist(
                self.current_user, 
                self.playlist_name, 
                video_id
            )
            if success:
                print(message)
                self._remove_song_card(song_data)
            else:
                print(f"Failed to remove song: {message}")
    
    def _remove_song_card(self, song_data):
        """Remove a song card from the UI"""
        # Find and remove the card
        for i, card in enumerate(self.cards):
            if hasattr(card, '_song_data') and card._song_data.get('videoId') == song_data.get('videoId'):
                # Remove the card and its separator
                card.destroy()
                self.cards.pop(i)
                
                # Remove separator if it exists
                separator = self.scrollable_frame.grid_slaves(row=i*2 + 1, column=0)
                if separator:
                    separator[0].destroy()
                
                # Update the remaining cards' grid positions
                for j in range(i, len(self.cards)):
                    self.cards[j].grid(row=j*2, column=0, sticky="nsew", padx=15, pady=5)
                    # Update separator position for remaining cards
                    if j < len(self.cards) - 1:
                        # Find the separator that should be at position j*2 + 1
                        separators_to_move = self.scrollable_frame.grid_slaves(row=(j+1)*2 + 1, column=0)
                        for sep in separators_to_move:
                            if isinstance(sep, ctk.CTkFrame) and sep.cget("height") == 1:
                                sep.grid(row=j*2 + 1, column=0, sticky="ew", padx=20, pady=2)
                
                # Check if we should show empty state
                if len(self.cards) == 0:
                    if self.playlist_name == "Saved Songs":
                        self.show_empty_state("No liked songs yet")
                    else:
                        self.show_empty_state(f"Playlist '{self.playlist_name}' is empty")
                else:
                    # Update scroll region after removal
                    self.after_idle(self._update_scroll_region)
                break
    
    def _on_canvas_configure(self, event):
        """Update the canvas window width when the canvas is resized"""
        if self._resize_in_progress:
            return
            
        if event.width > 1:  # Ensure we have a valid width
            self.canvas.itemconfig("scrollable_frame", width=event.width)
            
            # Update scroll region after configuring width
            self.after_idle(self._update_scroll_region)
    
    def _update_scroll_region(self):
        """Enable scrolling only when content truly exceeds the canvas height."""
        try:
            # Force layout calculations
            self.scrollable_frame.update_idletasks()

            # Use canvas bbox for precise content height
            bbox = self.canvas.bbox("all")
            content_height_raw = (bbox[3] - bbox[1]) if bbox else 0
            canvas_height = self.canvas.winfo_height()

            # Allow a small margin so an item at the bottom can still scroll up
            margin = 2
            bottom_padding = 60  # extra space only when content overflows

            if content_height_raw <= max(0, canvas_height - margin):
                # Content fits – disable scrolling
                self.canvas.configure(scrollregion=(0, 0, 0, 0))
                self.scrollbar.grid_remove()
                print("[DEBUG] Content fits, scrolling disabled but events remain bound")
            else:
                # Content exceeds canvas – enable scrolling, add bottom padding
                if bbox:
                    padded_bbox = (bbox[0], bbox[1], bbox[2], bbox[3] + bottom_padding)
                    self.canvas.configure(scrollregion=padded_bbox)
                self.scrollbar.grid(row=0, column=1, sticky="ns")
                print("[DEBUG] Content exceeds canvas, scrolling enabled")

        except Exception as e:
            print(f"[DEBUG] Error updating scroll region: {e}")

    def _on_window_configure(self, event):
        """Handle window resize with debounce"""
        if self._resize_after_id:
            self.after_cancel(self._resize_after_id)
            
        self._resize_after_id = self.after(200, self._process_resize)
    
    def _process_resize(self):
        """Process resize after a short delay to prevent excessive updates"""
        self._resize_in_progress = True
        try:
            # Update card layouts first
            for card in self.cards:
                if hasattr(card, '_title') and card._title.winfo_exists():
                    available_width = max(100, card.winfo_width() - 220)
                    card._title.configure(wraplength=available_width)
            
            # Then update scroll region
            self._update_scroll_region()
            
        finally:
            self._resize_in_progress = False
            self._resize_after_id = None
    
    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling with better logic"""
        try:
            # Check if scrolling is actually needed
            scrollregion = self.canvas.cget("scrollregion")
            if not scrollregion or scrollregion == "0 0 0 0":
                # No scroll region set, don't scroll
                return "break"
            
            # Parse scroll region
            x1, y1, x2, y2 = map(float, scrollregion.split())
            content_height = y2 - y1
            canvas_height = self.canvas.winfo_height()
            
            # Only scroll if content is larger than canvas
            if content_height <= canvas_height:
                return "break"
            
            # Handle different platforms
            if hasattr(event, 'delta') and event.delta:
                # Windows and MacOS
                delta = int(-1 * (event.delta / 120))
            elif hasattr(event, 'num'):
                # Linux
                if event.num == 4:
                    delta = -1  # scroll up
                elif event.num == 5:
                    delta = 1   # scroll down
                else:
                    return "break"
            else:
                return "break"
            
            # Perform the scroll
            self.canvas.yview_scroll(delta, "units")
            
            # Prevent event from propagating further
            return "break"
            
        except Exception as e:
            print(f"[DEBUG] Error in mouse wheel handler: {e}")
            return "break"
    
    def _on_destroy(self, event=None):
        """Cleanup when the object is destroyed"""
        if hasattr(self, 'executor'):
            try:
                self.executor.shutdown(wait=False)
            except Exception:
                pass
        
        if hasattr(self, 'session'):
            try:
                self.session.close()
            except Exception:
                pass
    
    def __del__(self):
        """Cleanup when the object is destroyed"""
        if hasattr(self, 'executor'):
            try:
                self.executor.shutdown(wait=False)
            except Exception:
                pass
        
        if hasattr(self, 'session'):
            try:
                self.session.close()
            except Exception:
                pass