import customtkinter as ctk
from PIL import Image, ImageTk
import requests
from io import BytesIO
import threading
import yt_dlp
import re
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from playerClass import MusicPlayerContainer
from FirebaseClass import FirebaseManager

class PlaylistScreen(ctk.CTkFrame):
    def __init__(self, parent, current_user, song_selection_callback, playlist_name="Saved Songs", back_callback=None, *args, **kwargs):
        print(f"[DEBUG] PlaylistScreen.__init__ called with playlist_name: {playlist_name}")
        super().__init__(parent, *args, **kwargs)
        self.current_user = current_user
        self.song_selection_callback = song_selection_callback
        self.playlist_name = playlist_name
        self.back_callback = back_callback
        self.firebase_manager = FirebaseManager() if current_user else None
        self.configure(fg_color="transparent")
        
        print(f"[DEBUG] current_user: {current_user}")
        print(f"[DEBUG] firebase_manager: {self.firebase_manager}")
        
        # Track window resize state
        self._resize_in_progress = False
        self._resize_after_id = None
        
        # Song data cache
        self.song_data_cache = {}
        self.loading_songs = False
        
        # Thread pool for parallel processing
        self.executor = ThreadPoolExecutor(max_workers=5)
        
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
        
        print("[DEBUG] Loading liked songs...")
        # Load liked songs
        self.load_liked_songs()
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
        
        # Bind events
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.bind("<Configure>", self._on_window_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
        # Initialize cards list
        self.cards = []
        print("[DEBUG] create_content_area completed")
    
    def extract_video_id(self, url):
        """Extract video ID from various YouTube URL formats"""
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def get_instant_song_data(self, url):
        """Extract basic song info instantly from URL and YouTube's basic API"""
        try:
            video_id = self.extract_video_id(url)
            if not video_id:
                return None
            
            # Check cache first
            if video_id in self.song_data_cache:
                return self.song_data_cache[video_id]
            
            # Create basic song data with video ID
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
            
            # Try multiple fast methods in parallel
            import concurrent.futures
            
            def get_oembed_data():
                try:
                    oembed_url = f"https://www.youtube.com/oembed?url={url}&format=json"
                    response = requests.get(oembed_url, timeout=2)
                    if response.status_code == 200:
                        data = response.json()
                        return {
                            'title': data.get('title', 'Unknown Title')[:100],
                            'uploader': data.get('author_name', 'Unknown')[:50]
                        }
                except Exception as e:
                    print(f"oEmbed failed for {video_id}: {e}")
                return {}
            
            def get_youtube_api_data():
                """Try to get duration and view count from YouTube's player API (fast)"""
                try:
                    # YouTube's player config API (faster than yt-dlp)
                    api_url = f"https://www.youtube.com/watch?v={video_id}"
                    response = requests.get(api_url, timeout=3, headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    })
                    
                    if response.status_code == 200:
                        content = response.text
                        
                        # Extract duration from page source (fast method)
                        duration_match = re.search(r'"lengthSeconds":"(\d+)"', content)
                        if duration_match:
                            duration_seconds = int(duration_match.group(1))
                            formatted_duration = self.format_duration(duration_seconds)
                        else:
                            formatted_duration = None
                        
                        # Extract view count from page source
                        view_match = re.search(r'"viewCount":"(\d+)"', content)
                        if view_match:
                            view_count = int(view_match.group(1))
                            formatted_views = self.format_views(view_count)
                        else:
                            formatted_views = None
                        
                        return {
                            'duration': formatted_duration,
                            'view_count': formatted_views
                        }
                except Exception as e:
                    print(f"YouTube API scraping failed for {video_id}: {e}")
                return {}
            
            def get_innertube_data():
                """Alternative fast method using YouTube's internal API"""
                try:
                    # YouTube's innertube API (used by the website)
                    innertube_url = "https://www.youtube.com/youtubei/v1/player"
                    payload = {
                        "context": {
                            "client": {
                                "clientName": "WEB",
                                "clientVersion": "2.20231201.01.00"
                            }
                        },
                        "videoId": video_id
                    }
                    
                    response = requests.post(
                        innertube_url,
                        json=payload,
                        timeout=2,
                        headers={'Content-Type': 'application/json'}
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        video_details = data.get('videoDetails', {})
                        
                        duration_seconds = video_details.get('lengthSeconds')
                        view_count = video_details.get('viewCount')
                        
                        result = {}
                        if duration_seconds:
                            result['duration'] = self.format_duration(int(duration_seconds))
                        if view_count:
                            result['view_count'] = self.format_views(int(view_count))
                        
                        return result
                except Exception as e:
                    print(f"Innertube API failed for {video_id}: {e}")
                return {}
            
            # Execute all methods in parallel for maximum speed
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                future_oembed = executor.submit(get_oembed_data)
                future_youtube = executor.submit(get_youtube_api_data)
                future_innertube = executor.submit(get_innertube_data)
                
                # Collect results with short timeout
                try:
                    oembed_data = future_oembed.result(timeout=2)
                    song_data.update(oembed_data)
                except:
                    pass
                
                try:
                    youtube_data = future_youtube.result(timeout=3)
                    if youtube_data.get('duration'):
                        song_data['duration'] = youtube_data['duration']
                    if youtube_data.get('view_count'):
                        song_data['view_count'] = youtube_data['view_count']
                except:
                    pass
                
                try:
                    innertube_data = future_innertube.result(timeout=2)
                    # Only use innertube data if we don't have it from youtube scraping
                    if not song_data.get('duration') or song_data['duration'] == "Loading...":
                        if innertube_data.get('duration'):
                            song_data['duration'] = innertube_data['duration']
                    if not song_data.get('view_count') or song_data['view_count'] == "Loading...":
                        if innertube_data.get('view_count'):
                            song_data['view_count'] = innertube_data['view_count']
                except:
                    pass
            
            # Check if we got everything we need
            has_duration = song_data.get('duration') and song_data['duration'] != "Loading..."
            has_views = song_data.get('view_count') and song_data['view_count'] != "Loading..."
            has_title = song_data.get('title') and song_data['title'] != "Loading..."
            has_uploader = song_data.get('uploader') and song_data['uploader'] != "Loading..."
            
            # If we got most of the data instantly, mark as not loading
            if has_title and has_uploader and (has_duration or has_views):
                song_data['is_loading'] = False
            
            # Cache the result if we have good data
            if not song_data.get('is_loading', True):
                self.song_data_cache[video_id] = song_data
            
            return song_data
            
        except Exception as e:
            print(f"Error extracting instant song data from URL {url}: {e}")
            return None
    
    def enhance_song_data_batch(self, song_data_list):
        """Enhanced batch processing - only for songs that still need data"""
        def enhance_single_song(song_data):
            try:
                video_id = song_data['videoId']
                url = song_data['url']
                
                # Skip if already fully loaded
                if not song_data.get('is_loading', False):
                    # Check if we're missing critical data
                    needs_enhancement = (
                        song_data.get('duration') in ["Loading...", None, ""] or
                        song_data.get('view_count') in ["Loading...", None, ""] or
                        song_data.get('title') in ["Loading...", None, ""] or
                        song_data.get('uploader') in ["Loading...", None, ""]
                    )
                    if not needs_enhancement:
                        return song_data
                
                print(f"[DEBUG] Enhancing song {video_id} with yt-dlp (fallback)...")
                
                # Only use yt-dlp as fallback for missing data
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'extract_flat': False,
                    'skip_download': True,
                    'ignoreerrors': True,
                    'geo_bypass': True,
                    'noplaylist': True,
                    'socket_timeout': 8,
                    'retries': 1,
                    'no_check_certificate': True,
                    'extractor_args': {
                        'youtube': {
                            'skip': ['dash', 'hls'],
                        }
                    }
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    
                    if info:
                        # Only update missing fields
                        enhanced_data = song_data.copy()
                        
                        if enhanced_data.get('title') in ["Loading...", None, ""]:
                            enhanced_data['title'] = info.get('title', 'Unknown Title')[:100]
                        
                        if enhanced_data.get('uploader') in ["Loading...", None, ""]:
                            enhanced_data['uploader'] = info.get('uploader', 'Unknown')[:50]
                        
                        if enhanced_data.get('duration') in ["Loading...", None, ""]:
                            duration_seconds = info.get('duration', 0)
                            enhanced_data['duration'] = self.format_duration(duration_seconds)
                        
                        if enhanced_data.get('view_count') in ["Loading...", None, ""]:
                            enhanced_data['view_count'] = self.format_views(info.get('view_count', 0))
                        
                        enhanced_data['is_loading'] = False
                        
                        # Cache the enhanced result
                        self.song_data_cache[video_id] = enhanced_data
                        return enhanced_data
                
                # If yt-dlp fails, mark as not loading and set defaults for missing fields
                song_data['is_loading'] = False
                if song_data.get('duration') in ["Loading...", None, ""]:
                    song_data['duration'] = "0:00"
                if song_data.get('view_count') in ["Loading...", None, ""]:
                    song_data['view_count'] = "0 views"
                if song_data.get('title') in ["Loading...", None, ""]:
                    song_data['title'] = f"Video {video_id[:8]}"
                if song_data.get('uploader') in ["Loading...", None, ""]:
                    song_data['uploader'] = "Unknown"
                
                return song_data
                
            except Exception as e:
                print(f"Error enhancing song data for {song_data.get('videoId', 'unknown')}: {e}")
                song_data['is_loading'] = False
                # Set defaults for any missing fields
                if song_data.get('duration') in ["Loading...", None, ""]:
                    song_data['duration'] = "0:00"
                if song_data.get('view_count') in ["Loading...", None, ""]:
                    song_data['view_count'] = "0 views"
                return song_data
        
        # Filter songs that actually need enhancement
        songs_needing_enhancement = [
            song for song in song_data_list 
            if song.get('is_loading', False) or 
            song.get('duration') in ["Loading...", None, ""] or
            song.get('view_count') in ["Loading...", None, ""]
        ]
        
        if not songs_needing_enhancement:
            return song_data_list
        
        # Process only songs that need enhancement
        enhanced_songs = song_data_list.copy()  # Start with original list
        
        # Process in smaller batches for better reliability
        batch_size = 2
        
        for i in range(0, len(songs_needing_enhancement), batch_size):
            batch = songs_needing_enhancement[i:i + batch_size]
            futures = []
            
            for song_data in batch:
                future = self.executor.submit(enhance_single_song, song_data)
                futures.append((future, song_data))
            
            # Wait for batch completion and update UI
            for future, original_song_data in futures:
                try:
                    enhanced_song_data = future.result(timeout=10)
                    
                    # Update the enhanced_songs list
                    for j, song in enumerate(enhanced_songs):
                        if song.get('videoId') == enhanced_song_data.get('videoId'):
                            enhanced_songs[j] = enhanced_song_data
                            break
                    
                    # Update UI immediately
                    self.after(0, lambda data=enhanced_song_data: self.update_song_card(data))
                    
                except Exception as e:
                    print(f"Error processing song: {e}")
                    # Update with defaults
                    original_song_data['is_loading'] = False
                    if original_song_data.get('duration') in ["Loading...", None, ""]:
                        original_song_data['duration'] = "0:00"
                    if original_song_data.get('view_count') in ["Loading...", None, ""]:
                        original_song_data['view_count'] = "0 views"
                    
                    self.after(0, lambda data=original_song_data: self.update_song_card(data))
        
        return enhanced_songs
    
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
        """Build the details text for a song card"""
        details = []
        
        # Add uploader if available
        uploader = song_data.get('uploader')
        if uploader and uploader not in ["Loading...", "Unknown", ""]:
            details.append(uploader)
        
        # Add duration if available - prioritize this
        duration = song_data.get('duration')
        if duration and duration not in ["Loading...", "0:00", ""]:
            details.append(duration)
        elif not song_data.get('is_loading', False):
            # If not loading and no duration, add placeholder
            details.append("Duration N/A")
        
        # Add view count if available
        view_count = song_data.get('view_count')
        if view_count and view_count not in ["Loading...", "0 views", ""]:
            details.append(view_count)
        
        if details:
            return " • ".join(details)
        elif song_data.get('is_loading', False):
            return "Loading details..."
        else:
            return "Details unavailable"
    
    def load_liked_songs(self):
        """Load liked songs with instant display and background enhancement"""
        print(f"[DEBUG] load_liked_songs called")
        
        if not self.current_user or not self.firebase_manager:
            print("[DEBUG] User not logged in or no firebase manager")
            self.show_empty_state("Please log in to view your liked songs")
            return
        
        print("[DEBUG] Showing loading state...")
        self.show_loading_state()
        
        def load_songs_instantly():
            print("[DEBUG] load_songs_instantly started")
            try:
                # Get liked URLs from Firebase
                liked_urls = self.firebase_manager.get_user_liked_songs(self.current_user)
                print(f"[DEBUG] Got {len(liked_urls) if liked_urls else 0} liked URLs")
                
                if not liked_urls:
                    self.after(0, lambda: self.show_empty_state("No liked songs yet"))
                    return
                
                # Get instant basic data for all songs in parallel
                instant_song_data = []
                from concurrent.futures import ThreadPoolExecutor, as_completed
                with ThreadPoolExecutor(max_workers=8) as executor:
                    future_to_url = {executor.submit(self.get_instant_song_data, url): url for url in liked_urls}
                    for future in as_completed(future_to_url):
                        song_data = future.result()
                        if song_data:
                            instant_song_data.append(song_data)
                
                print(f"[DEBUG] Got instant data for {len(instant_song_data)} songs")
                
                # Display instantly
                self.after(0, lambda: self.display_songs(instant_song_data))
                
                # Start background enhancement
                if instant_song_data:
                    threading.Thread(
                        target=lambda: self.enhance_song_data_batch(instant_song_data),
                        daemon=True
                    ).start()
                
            except Exception as e:
                print(f"[DEBUG] Error in load_songs_instantly: {e}")
                import traceback
                traceback.print_exc()
                self.after(0, lambda: self.show_error_state("Failed to load liked songs"))
        
        # Start loading in background thread
        threading.Thread(target=load_songs_instantly, daemon=True).start()

    def load_playlist_songs(self, playlist_data):
        """Load songs from a specific playlist with instant display"""
        if not playlist_data or not playlist_data.get('songs'):
            self.show_empty_state("This playlist is empty")
            return
        
        self.show_loading_state()
        
        def load_songs_instantly():
            try:
                instant_song_data = []
                
                for song_data in playlist_data['songs']:
                    # If song_data already has complete info, use it
                    if ('videoId' in song_data and 'title' in song_data and 
                        not song_data.get('is_loading', False)):
                        instant_song_data.append(song_data)
                    elif 'url' in song_data:
                        # Get instant data from URL
                        processed_data = self.get_instant_song_data(song_data['url'])
                        if processed_data:
                            instant_song_data.append(processed_data)
                
                # Display instantly
                self.after(0, lambda: self.display_songs(instant_song_data))
                
                # Enhance songs that need it
                songs_to_enhance = [s for s in instant_song_data if s.get('is_loading', False)]
                if songs_to_enhance:
                    threading.Thread(
                        target=lambda: self.enhance_song_data_batch(songs_to_enhance),
                        daemon=True
                    ).start()
                
            except Exception as e:
                print(f"Error loading playlist songs: {e}")
                self.after(0, lambda: self.show_error_state("Failed to load playlist songs"))
        
        threading.Thread(target=load_songs_instantly, daemon=True).start()
    
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
            text="Loading your liked songs...",
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
        
        # Create song cards
        for idx, song_data in enumerate(song_data_list):
            self._add_song_card(song_data, idx)
        
        # Remove the last separator if it exists (since we add separators for all items)
        if len(song_data_list) > 0:
            last_separator_row = (len(song_data_list) - 1) * 2 + 1
            separators = self.scrollable_frame.grid_slaves(row=last_separator_row, column=0)
            for separator in separators:
                if isinstance(separator, ctk.CTkFrame) and separator.cget("height") == 1:
                    separator.destroy()
        
        # Update scroll region
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        print("[DEBUG] display_songs completed")

    def _add_song_card(self, song_data, idx):
        """Create a single song card"""
        # Create main card frame with dynamic width
        card = ctk.CTkFrame(
            self.scrollable_frame,
            fg_color="#222222",
            corner_radius=10,
            height=100
        )
        
        # Store card reference and song data
        card._title = None  # Will store the title widget reference
        card._details_label = None  # Will store the details widget reference
        card._song_data = song_data  # Store song data with the card
        
        # Configure grid for the card to take full width
        card.grid(row=idx*2, column=0, sticky="nsew", padx=15, pady=5)
        card.grid_columnconfigure(1, weight=1)  # Make the content area expandable
        card.grid_columnconfigure(2, weight=0, minsize=70)  # Make the button column just wide enough
        card.grid_columnconfigure(3, weight=0, minsize=50)  # Make room for like button
        
        # Thumbnail container with fixed aspect ratio
        thumb_container = ctk.CTkFrame(card, fg_color="transparent", width=120, height=80)
        thumb_container.grid(row=0, column=0, rowspan=2, padx=10, pady=10, sticky="nsw")
        thumb_container.grid_propagate(False)  # Prevent container from resizing
        
        # Thumbnail label
        thumb = ctk.CTkLabel(thumb_container, text="")
        thumb.pack(expand=True, fill="both")
        
        # Load thumbnail in background
        def load_image_async():
            try:
                response = requests.get(song_data['thumbnail_url'], timeout=5)
                img = Image.open(BytesIO(response.content))
                img.thumbnail((120, 80), Image.Resampling.LANCZOS)
                tk_image = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                def update_image():
                    if thumb.winfo_exists():  # Check if widget still exists
                        thumb.configure(image=tk_image)
                        thumb.image = tk_image
                self.after(0, update_image)
            except Exception as e:
                print(f"Error loading image: {e}")
        
        threading.Thread(target=load_image_async, daemon=True).start()
        
        # Content frame that expands with window
        content_frame = ctk.CTkFrame(card, fg_color="transparent")
        content_frame.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(0, 20), pady=10)
        content_frame.columnconfigure(0, weight=1)
        
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
            wraplength=0  # Will be updated on resize
        )
        title.grid(row=0, column=0, sticky="nsw", pady=(0, 5))
        
        # Store title reference on card for later updates
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
        
        # Store details label reference for updates
        card._details_label = details_label
        
        # Unlike/Remove button (different behavior for Saved Songs vs custom playlists)
        if self.playlist_name == "Saved Songs":
            # For Saved Songs, show unlike button
            unlike_button = ctk.CTkButton(
                card,
                text="♥",
                width=40,
                height=40,
                corner_radius=20,
                fg_color="#FF6B6B",
                hover_color="#FF5252",
                text_color="#FFFFFF",
                font=ctk.CTkFont(size=14),
                command=lambda: self._on_unlike_button_clicked(song_data, unlike_button)
            )
        else:
            # For custom playlists, show remove button
            unlike_button = ctk.CTkButton(
                card,
                text="🗑",
                width=40,
                height=40,
                corner_radius=20,
                fg_color="#FF6B6B",
                hover_color="#FF5252",
                text_color="#FFFFFF",
                font=ctk.CTkFont(size=14),
                command=lambda: self._on_remove_from_playlist_clicked(song_data, unlike_button)
            )
        
        unlike_button.grid(row=0, column=2, rowspan=2, padx=(0, 10), pady=15, sticky="nsew")
        
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
        
        # Add a separator between items (we'll add it for all items except we'll handle the last one in display_songs)
        separator = ctk.CTkFrame(
            self.scrollable_frame,
            height=1,
            fg_color="#333333"
        )
        separator.grid(row=idx*2 + 1, column=0, sticky="ew", padx=20, pady=2)
        
        self.cards.append(card)
        
        # Update wraplength on window resize
        def update_wraplength(event):
            # Calculate available width for the title (total width - thumbnail - buttons - paddings)
            available_width = max(100, card.winfo_width() - 270)  # 270 = thumbnail(120) + unlike button(40) + play button(60) + paddings(50)
            title.configure(wraplength=available_width)
            
        # Bind to card resize
        card.bind('<Configure>', update_wraplength)
    
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
    
    def _on_unlike_button_clicked(self, song_data, unlike_button):
        """Handle unlike button click"""
        if not self.current_user or not self.firebase_manager:
            print("User not logged in")
            return
        
        # Unlike the song
        success, is_liked, message = self.firebase_manager.toggle_song_like(self.current_user, song_data)
        
        if success and not is_liked:  # Song was unliked
            # Remove the card from the UI
            self._remove_song_card(song_data)
            print(message)
        else:
            print(f"Error: {message}")
    
    def _remove_song_card(self, song_data):
        """Remove a song card from the UI"""
        # Find and remove the card
        for i, card in enumerate(self.cards):
            if hasattr(card, '_song_data') and card._song_data.get('videoId') == song_data.get('videoId'):
                # Remove the card and its separator
                card.destroy()
                self.cards.pop(i)
                
                # Remove separator if it exists
                if i < len(self.cards):  # If not the last card
                    separator = self.scrollable_frame.grid_slaves(row=i*2 + 1, column=0)
                    if separator:
                        separator[0].destroy()
                
                # Update the remaining cards' grid positions
                for j in range(i, len(self.cards)):
                    self.cards[j].grid(row=j*2, column=0, sticky="nsew", padx=15, pady=5)
                    # Update separator position
                    if j < len(self.cards) - 1:
                        separator = self.scrollable_frame.grid_slaves(row=j*2 + 1, column=0)
                        if separator:
                            separator[0].grid(row=j*2 + 1, column=0, sticky="ew", padx=20, pady=2)
                
                # Update scroll region
                self.canvas.configure(scrollregion=self.canvas.bbox("all"))
                break
    
    def _on_remove_from_playlist_clicked(self, song_data, remove_button):
        """Handle remove from playlist button click"""
        # For custom playlists, we need to remove from the local playlist data
        # This would need to be implemented in the main app
        print(f"Remove '{song_data.get('title')}' from playlist '{self.playlist_name}'")
        
        # For now, just remove from UI
        self._remove_song_card(song_data)
    
    def _on_canvas_configure(self, event):
        """Update the canvas window width when the canvas is resized"""
        if self._resize_in_progress:
            return
            
        if event.width > 1:  # Ensure we have a valid width
            self.canvas.itemconfig("scrollable_frame", width=event.width)
    
    def _on_window_configure(self, event):
        """Handle window resize with debounce"""
        if self._resize_after_id:
            self.after_cancel(self._resize_after_id)
            
        self._resize_after_id = self.after(200, self._process_resize)
    
    def _process_resize(self):
        """Process resize after a short delay to prevent excessive updates"""
        self._resize_in_progress = True
        try:
            # Update canvas scroll region
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            
            # Update card layouts
            for card in self.cards:
                if hasattr(card, '_title') and card._title.winfo_exists():
                    available_width = max(100, card.winfo_width() - 220)
                    card._title.configure(wraplength=available_width)
        finally:
            self._resize_in_progress = False
            self._resize_after_id = None
    
    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    
    def __del__(self):
        """Cleanup when the object is destroyed"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)