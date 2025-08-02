import customtkinter as ctk
from PIL import Image, ImageTk
import requests
from io import BytesIO
import threading
import yt_dlp
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
    
    def load_liked_songs(self):
        """Load liked songs from Firebase - instant loading with full details"""
        print(f"[DEBUG] load_liked_songs called")
        print(f"[DEBUG] current_user: {self.current_user}")
        print(f"[DEBUG] firebase_manager: {self.firebase_manager}")
        
        if not self.current_user or not self.firebase_manager:
            print("[DEBUG] User not logged in or no firebase manager")
            self.show_empty_state("Please log in to view your liked songs")
            return
        
        print("[DEBUG] Showing loading state...")
        # Show loading state
        self.show_loading_state()
        
        # Load liked URLs and get full details instantly
        def load_songs_instant():
            print("[DEBUG] load_songs_instant started")
            try:
                print(f"[DEBUG] Calling firebase_manager.get_user_liked_songs({self.current_user})")
                liked_urls = self.firebase_manager.get_user_liked_songs(self.current_user)
                print(f"[DEBUG] liked_urls: {liked_urls}")
                
                if not liked_urls:
                    print("[DEBUG] No liked URLs found")
                    self.after(0, lambda: self.show_empty_state("No liked songs yet"))
                    return
                
                # Process URLs to get full song data instantly
                song_data_list = []
                for url in liked_urls:
                    print(f"[DEBUG] Processing URL: {url}")
                    song_data = self.get_song_data_from_url_fast(url)
                    if song_data:
                        song_data_list.append(song_data)
                        print(f"[DEBUG] Added song data: {song_data.get('title', 'Unknown')}")
                    else:
                        print(f"[DEBUG] Failed to get song data for URL: {url}")
                
                print(f"[DEBUG] Final song_data_list length: {len(song_data_list)}")
                # Update UI with song data
                self.after(0, lambda: self.display_songs(song_data_list))
                
            except Exception as e:
                print(f"[DEBUG] Error in load_songs_instant: {e}")
                import traceback
                traceback.print_exc()
                self.after(0, lambda: self.show_error_state("Failed to load liked songs"))
        
        # Run instant loading
        load_songs_instant()

    def get_song_data_from_url_fast(self, url):
        """Extract song data from YouTube URL using optimized yt-dlp settings"""
        try:
            # Extract video ID from URL
            if 'youtube.com/watch?v=' in url:
                video_id = url.split('v=')[1].split('&')[0]
            else:
                return None
            
            # Check cache first
            if video_id in self.song_data_cache:
                return self.song_data_cache[video_id]
            
            # Configure yt-dlp options for fast extraction
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,  # Get full info
                'skip_download': True,
                'ignoreerrors': True,
                'geo_bypass': True,
                'noplaylist': True,
                'socket_timeout': 3,  # Very short timeout
                'retries': 0,  # No retries for speed
                'no_check_certificate': True,  # Skip certificate check
                'extractor_args': {
                    'youtube': {
                        'skip': ['dash', 'hls'],  # Skip some formats
                    }
                }
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    return None
                
                # Create song data object with full details
                song_data = {
                    'title': info.get('title', 'Unknown Title')[:100],
                    'thumbnail_url': f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
                    'videoId': video_id,
                    'uploader': info.get('uploader', 'Unknown')[:50],
                    'duration': self.format_duration(info.get('duration', 0)),
                    'view_count': self.format_views(info.get('view_count', 0)),
                    'url': url
                }
                
                # Cache the result
                self.song_data_cache[video_id] = song_data
                return song_data
                
        except Exception as e:
            print(f"Error extracting song data from URL {url}: {e}")
            # Return basic data if yt-dlp fails
            return self.get_basic_song_data_from_url(url)

    def get_basic_song_data_from_url(self, url):
        """Extract basic song data from YouTube URL as fallback"""
        try:
            # Extract video ID from URL
            if 'youtube.com/watch?v=' in url:
                video_id = url.split('v=')[1].split('&')[0]
            else:
                return None
            
            # Create basic song data object
            song_data = {
                'title': f"Video {video_id}",
                'thumbnail_url': f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
                'videoId': video_id,
                'uploader': "Unknown",
                'duration': "0:00",
                'view_count': "0 views",
                'url': url
            }
            
            return song_data
                
        except Exception as e:
            print(f"Error extracting basic song data from URL {url}: {e}")
            return None

    def load_playlist_songs(self, playlist_data):
        """Load songs from a specific playlist"""
        if not playlist_data or not playlist_data.get('songs'):
            self.show_empty_state("This playlist is empty")
            return
        
        # Show loading state
        self.show_loading_state()
        
        # Process playlist songs instantly
        def load_songs_instant():
            try:
                song_data_list = []
                for song_data in playlist_data['songs']:
                    # If song_data already has the required fields, use it directly
                    if 'videoId' in song_data and 'title' in song_data:
                        song_data_list.append(song_data)
                    else:
                        # Otherwise, try to get data from URL
                        if 'url' in song_data:
                            processed_data = self.get_song_data_from_url_fast(song_data['url'])
                            if processed_data:
                                song_data_list.append(processed_data)
                
                # Update UI with song data
                self.after(0, lambda: self.display_songs(song_data_list))
                
            except Exception as e:
                print(f"Error loading playlist songs: {e}")
                self.after(0, lambda: self.show_error_state("Failed to load playlist songs"))
        
        # Run instant loading
        load_songs_instant()
    
    def get_song_data_from_url(self, url):
        """Extract song data from YouTube URL using yt-dlp - legacy method"""
        try:
            # Extract video ID from URL
            if 'youtube.com/watch?v=' in url:
                video_id = url.split('v=')[1].split('&')[0]
            else:
                return None
            
            # Check cache first
            if video_id in self.song_data_cache:
                return self.song_data_cache[video_id]
            
            # Configure yt-dlp options
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'skip_download': True,
                'ignoreerrors': True,
                'geo_bypass': True,
                'noplaylist': True,
                'socket_timeout': 10,
                'retries': 1,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    return None
                
                # Create song data object
                song_data = {
                    'title': info.get('title', 'Unknown Title')[:100],
                    'thumbnail_url': f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
                    'videoId': video_id,
                    'uploader': info.get('uploader', 'Unknown')[:50],
                    'duration': self.format_duration(info.get('duration', 0)),
                    'view_count': self.format_views(info.get('view_count', 0)),
                    'url': url
                }
                
                # Cache the result
                self.song_data_cache[video_id] = song_data
                return song_data
                
        except Exception as e:
            print(f"Error extracting song data from URL {url}: {e}")
            return None
    
    def format_duration(self, seconds):
        """Format duration in seconds to MM:SS or HH:MM:SS"""
        if not seconds or seconds <= 0:
            return "0:00"
        
        minutes, secs = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"
    
    def format_views(self, view_count):
        """Format view count to readable format"""
        if not view_count or view_count <= 0:
            return "0 views"
        
        if view_count >= 1_000_000:
            return f"{view_count // 100000 / 10:.1f}M views"
        elif view_count >= 1_000:
            return f"{view_count // 100 / 10:.1f}K views"
        else:
            return f"{view_count} views"
    
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
            text="",
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
        
        # Configure grid for scrollable frame
        self.scrollable_frame.columnconfigure(0, weight=1)
        
        # Create song cards
        for idx, song_data in enumerate(song_data_list):
            self._add_song_card(song_data, idx)
        
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
        title = ctk.CTkLabel(
            content_frame,
            text=song_data['title'],
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
            justify="left",
            wraplength=0  # Will be updated on resize
        )
        title.grid(row=0, column=0, sticky="nsw", pady=(0, 5))
        
        # Store title reference on card for later updates
        card._title = title
        
        # Additional info (uploader, duration, views)
        details = []
        if 'uploader' in song_data and song_data['uploader']:
            details.append(song_data['uploader'])
        if 'duration' in song_data and song_data['duration']:
            details.append(song_data['duration'])
        if 'view_count' in song_data and song_data['view_count']:
            details.append(song_data['view_count'])
            
        if details:
            details_text = " • ".join(details)
            details_label = ctk.CTkLabel(
                content_frame,
                text=details_text,
                font=ctk.CTkFont(size=14),
                text_color="gray",
                anchor="w",
                justify="left"
            )
            details_label.grid(row=1, column=0, sticky="nsw")
        
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
        
        # Add a separator between items
        if idx < len(self.cards) + 1:  # Check if not the last item
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
