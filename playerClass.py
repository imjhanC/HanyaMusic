import customtkinter as ctk
from PIL import Image, ImageTk
import requests
from io import BytesIO
import threading
import time
import vlc
import yt_dlp
import pygame

class MusicPlayerContainer(ctk.CTkFrame):
    def __init__(self, parent, song_data, playlist=None, current_index=0, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.song_data = song_data
        self.playlist = playlist or [song_data]  # Default to current song if no playlist
        self.current_index = current_index
        self.shuffled_playlist = None  # Store shuffled playlist
        self.shuffled_index = 0  # Current position in shuffled playlist
        self.is_playing = False
        self.current_time = 0
        self.total_duration = 0
        self.volume = 1.0
        self.shuffle_enabled = False
        self.repeat_enabled = False  # Repeat state
        # Video modal state
        self.video_visible = False
        self.video_window = None
        self.video_frame = None
        self.video_vlc_instance = None
        self.video_player = None
        self._video_sync_job = None
        self._root_configure_bind_id = None
        self._audio_was_playing_before_video = False
        
        # VLC and audio setup
        self.vlc_instance = None
        self.player = None
        self.media = None
        self.stream_url = None
        
        # Callback for song changes
        self.on_song_change = None
        self.on_close = None  # Callback for when player is closed
        
        # Initialize pygame mixer for better audio control
        pygame.mixer.init()
        
        # Configure the player container
        self.configure(fg_color="#000000")
        self.grid_propagate(False)  # Prevent the frame from shrinking to fit content
        self.configure(height=240)  # Set explicit height
        
        # Create the player layout
        self._create_player_layout()
        
        # Load and prepare the audio stream
        self._load_audio_stream()
        
        # Start progress update timer
        self._update_progress()
    
    def set_playlist(self, playlist, current_index=0):
        """Set the playlist and current song index"""
        self.playlist = playlist
        self.current_index = current_index
        self.song_data = playlist[current_index]
        self._update_song_info()
        self._load_audio_stream()
    
    def set_on_song_change_callback(self, callback):
        """Set callback function to be called when song changes"""
        self.on_song_change = callback
    
    def set_on_close_callback(self, callback):
        """Set callback function to be called when player is closed"""
        self.on_close = callback
    
    def _update_song_info(self):
        """Update the displayed song information"""
        self.song_title.configure(text=self.song_data.get('title', 'Unknown Title'))
        self.artist_name.configure(text=self.song_data.get('uploader', 'Unknown Artist'))
        self._load_thumbnail()
    
    def _load_audio_stream(self):
        """Load the audio stream URL using yt-dlp"""
        def load_stream_async():
            try:
                # Stop current playback if any
                if self.player:
                    self.player.stop()
                
                # Configure yt-dlp options for audio
                base_ydl_opts = {
                    'format': 'bestaudio[abr>0]/bestaudio/best',
                    'quiet': True,
                    'no_warnings': True,
                }
                
                # Extract video ID from song data
                video_id = self.song_data.get('videoId')
                if not video_id:
                    print("No video ID found")
                    return
                
                youtube_url = f"https://www.youtube.com/watch?v={video_id}"
                
                # Extract audio stream URL with cookie fallbacks if YouTube challenges
                def extract_with_cookies(url: str):
                    # First try without cookies
                    try:
                        with yt_dlp.YoutubeDL(base_ydl_opts) as ydl:
                            return ydl.extract_info(url, download=False)
                    except Exception as e_first:
                        lower_msg = str(e_first).lower()
                        need_cookies = ('confirm you' in lower_msg and 'bot' in lower_msg) or ('sign in to confirm' in lower_msg) or ('429' in lower_msg)
                        if not need_cookies:
                            raise
                        # Try common browsers for cookies
                        for browser_name in ['edge', 'chrome', 'chromium', 'brave', 'firefox']:
                            try:
                                opts = dict(base_ydl_opts)
                                opts['cookiesfrombrowser'] = (browser_name,)
                                with yt_dlp.YoutubeDL(opts) as ydl:
                                    return ydl.extract_info(url, download=False)
                            except Exception:
                                continue
                        # If all cookie attempts fail, re-raise the original
                        raise e_first

                info = extract_with_cookies(youtube_url)
                self.stream_url = info['url']
                self.total_duration = info.get('duration', 0)
                print(f"Loaded stream for: {info.get('title', 'Unknown Title')}")
                
                # Initialize VLC instance
                self.vlc_instance = vlc.Instance('--intf', 'dummy')
                self.player = self.vlc_instance.media_player_new()
                
                # Set media to the stream URL
                self.media = self.vlc_instance.media_new(self.stream_url)
                self.player.set_media(self.media)
                
                # Set initial volume
                self.player.audio_set_volume(int(self.volume * 100))
                try:
                    self.player.audio_set_mute(False)
                except Exception:
                    pass
                
                print("Audio stream loaded successfully")
                
                # Auto-play the song once loaded
                def start_playback():
                    if self.player:
                        self.player.play()
                        self.is_playing = True
                        self.play_btn.configure(text="⏸")
                        print("Auto-playing song")
                        try:
                            self.player.audio_set_mute(False)
                        except Exception:
                            pass
                
                # Schedule auto-play on main thread
                self.after(0, start_playback)
                # If video overlay is visible, reload and sync video too
                def prepare_video_if_needed():
                    if getattr(self, 'video_visible', False):
                        try:
                            # Reload video for the new track
                            self._load_video_stream()
                            # Enforce state after short delay for readiness
                            self.after(150, lambda: self._enforce_video_state(sync_time=True))
                        except Exception:
                            pass
                self.after(0, prepare_video_if_needed)
                
            except Exception as e:
                print(f"Error loading audio stream: {e}")
        
        # Load stream in background thread
        threading.Thread(target=load_stream_async, daemon=True).start()
    
    def _create_player_layout(self):
        # Main layout with 3 columns: thumbnail, controls, volume
        self.grid_columnconfigure(1, weight=1)
        
        # Create a header frame for the close/video buttons
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent", height=30)
        self.header_frame.grid(row=0, column=0, columnspan=3, sticky="nsew")
        self.header_frame.grid_propagate(False)
        
        # Video toggle button (aligned to left) ▲ to show, ▼ to hide
        self.video_toggle_btn = ctk.CTkButton(
            self.header_frame,
            text="▲ Switch to video",
            width=30,
            height=30,
            corner_radius=15,
            fg_color="transparent",
            hover_color="#333333",
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=16),
            command=self._toggle_video_modal
        )
        self.video_toggle_btn.pack(side="left", padx=5, pady=5)
        
        # Add close button to header frame (aligned to right)
        self.close_btn = ctk.CTkButton(
            self.header_frame,
            text="✖",
            width=30,
            height=30,
            corner_radius=15,
            fg_color="transparent",
            hover_color="#333333",
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=16),
            command=self._close_player
        )
        self.close_btn.pack(side="right", padx=5, pady=5)
        
        # Thumbnail section (left)
        self._create_thumbnail_section()
        
        # Controls section (center)
        self._create_controls_section()
        
        # Volume section (right) - horizontal layout
        self._create_volume_section()
    
    def _create_thumbnail_section(self):
        # Thumbnail container
        thumb_frame = ctk.CTkFrame(self, fg_color="transparent", width=100, height=100)
        thumb_frame.grid(row=1, column=0, padx=5, pady=10, sticky="nsw")
        thumb_frame.grid_propagate(False)
        
        # Thumbnail label
        self.thumbnail_label = ctk.CTkLabel(thumb_frame, text="")
        self.thumbnail_label.pack(expand=True, fill="both")
        
        # Load thumbnail
        self._load_thumbnail()
    
    def _create_controls_section(self):
        # Controls container
        controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        controls_frame.grid(row=1, column=1, sticky="nsew", padx=20, pady=10)
        controls_frame.grid_columnconfigure(0, weight=1)
        
        # Song info
        info_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        info_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        # Song title
        self.song_title = ctk.CTkLabel(
            info_frame,
            text=self.song_data.get('title', 'Unknown Title'),
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w"
        )
        self.song_title.pack(anchor="w")
        
        # Artist name
        self.artist_name = ctk.CTkLabel(
            info_frame,
            text=self.song_data.get('uploader', 'Unknown Artist'),
            font=ctk.CTkFont(size=14),
            text_color="gray",
            anchor="w"
        )
        self.artist_name.pack(anchor="w")
        
        # Progress bar
        self.progress_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        self.progress_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self.progress_frame.grid_columnconfigure(0, weight=1)
        
        # Time labels
        self.current_time_label = ctk.CTkLabel(
            self.progress_frame,
            text="0:00",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.current_time_label.grid(row=0, column=0, sticky="w")
        
        self.total_time_label = ctk.CTkLabel(
            self.progress_frame,
            text="0:00",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.total_time_label.grid(row=0, column=2, sticky="e")
        
        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame)
        self.progress_bar.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(5, 0))
        self.progress_bar.set(0)
        
        # Bind progress bar click for seeking
        self.progress_bar.bind("<Button-1>", self._on_progress_click)
        
        # Control buttons
        buttons_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        buttons_frame.grid(row=2, column=0, sticky="ew")
        
        # Center the buttons by using a grid layout
        buttons_frame.grid_columnconfigure(0, weight=1)
        buttons_frame.grid_columnconfigure(1, weight=0)
        buttons_frame.grid_columnconfigure(2, weight=0)
        buttons_frame.grid_columnconfigure(3, weight=0)
        buttons_frame.grid_columnconfigure(4, weight=0)
        buttons_frame.grid_columnconfigure(5, weight=0)
        buttons_frame.grid_columnconfigure(6, weight=1)
        # Repeat button (beside previous)
        self.repeat_btn = ctk.CTkButton(
            buttons_frame,
            text="🔁",
            width=40,
            height=40,
            corner_radius=20,
            fg_color="#333333",
            hover_color="#444444",
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=16),
            command=self._toggle_repeat
        )
        self.repeat_btn.grid(row=0, column=1, padx=5)
        # Previous button
        self.prev_btn = ctk.CTkButton(
            buttons_frame,
            text="⏮",
            width=40,
            height=40,
            corner_radius=20,
            fg_color="#333333",
            hover_color="#444444",
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=16),
            command=self._previous_song
        )
        self.prev_btn.grid(row=0, column=2, padx=5)
        # Play/Pause button
        self.play_btn = ctk.CTkButton(
            buttons_frame,
            text="▶",
            width=50,
            height=50,
            corner_radius=25,
            fg_color="#1DB954",
            hover_color="#1ed760",
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=20, weight="bold"),
            command=self._toggle_play_pause
        )
        self.play_btn.grid(row=0, column=3, padx=10)
        # Next button
        self.next_btn = ctk.CTkButton(
            buttons_frame,
            text="⏭",
            width=40,
            height=40,
            corner_radius=20,
            fg_color="#333333",
            hover_color="#444444",
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=16),
            command=self._next_song
        )
        self.next_btn.grid(row=0, column=4, padx=5)
        # Shuffle button
        self.shuffle_btn = ctk.CTkButton(
            buttons_frame,
            text="🔀",
            width=40,
            height=40,
            corner_radius=20,
            fg_color="#333333",
            hover_color="#444444",
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=16),
            command=self._toggle_shuffle
        )
        self.shuffle_btn.grid(row=0, column=5, padx=(20, 0))
    
    def _create_volume_section(self):
        # Volume container - horizontal layout
        volume_frame = ctk.CTkFrame(self, fg_color="transparent")
        volume_frame.grid(row=1, column=2, padx=15, pady=20, sticky="nse")
        
        # Volume icon and slider in horizontal layout
        volume_icon = ctk.CTkLabel(
            volume_frame,
            text="🔊",
            font=ctk.CTkFont(size=16)
        )
        volume_icon.pack(side="left", padx=(0, 10))
        
        # Volume slider - horizontal orientation
        self.volume_slider = ctk.CTkSlider(
            volume_frame,
            from_=0,
            to=1,
            number_of_steps=100,
            orientation="horizontal",
            width=100,
            command=self._on_volume_change
        )
        self.volume_slider.set(self.volume)
        self.volume_slider.pack(side="left")

    def _load_thumbnail(self):
        def load_image_async():
            try:
                response = requests.get(self.song_data['thumbnail_url'], timeout=5)
                img = Image.open(BytesIO(response.content))
                img.thumbnail((200, 200), Image.Resampling.LANCZOS)  # Increased size
                tk_image = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                def update_image():
                    if self.thumbnail_label.winfo_exists():
                        self.thumbnail_label.configure(image=tk_image)
                        self.thumbnail_label.image = tk_image
                self.after(0, update_image)
            except Exception as e:
                print(f"Error loading thumbnail: {e}")
        
        threading.Thread(target=load_image_async, daemon=True).start()
    
    def _toggle_play_pause(self):
        if not self.player:
            print("Player not ready yet")
            return
            
        if self.is_playing:
            # Pause
            self.player.pause()
            self.play_btn.configure(text="▶")
            self.is_playing = False
            # Pause video if visible
            if self.video_player:
                try:
                    self.video_player.set_pause(True)
                except Exception:
                    pass
        else:
            # Play
            self.player.play()
            self.play_btn.configure(text="⏸")
            self.is_playing = True
            # Play video if visible and sync
            if self.video_player:
                try:
                    self.video_player.set_pause(False)
                    self._sync_video_once()
                except Exception:
                    pass

    def _toggle_video_modal(self):
        """Show/hide a silent video modal over the results area, synced with audio."""
        if self.video_visible:
            self._hide_video_modal()
        else:
            self._show_video_modal()

    def _show_video_modal(self):
        try:
            if self.video_window and self.video_window.winfo_exists():
                return
            root = self.winfo_toplevel()
            # Create borderless topmost overlay
            self.video_window = ctk.CTkToplevel(master=root)
            self.video_window.overrideredirect(True)
            self.video_window.configure(fg_color="#000000")
            try:
                self.video_window.attributes("-topmost", True)
            except Exception:
                pass
            self.video_frame = ctk.CTkFrame(self.video_window, fg_color="#000000")
            self.video_frame.pack(fill="both", expand=True)
            self.video_visible = True
            self.video_toggle_btn.configure(text="▼ Switch to audio")
            self._position_video_modal()
            # Reposition on parent window moves/resizes
            try:
                if not self._root_configure_bind_id:
                    self._root_configure_bind_id = root.bind("<Configure>", lambda _e: self._position_video_modal())
            except Exception:
                pass
            # Prepare and play silent video; ensure audio player remains sound source
            # Explicitly unmute audio player in case a previous state muted it
            try:
                if self.player:
                    self.player.audio_set_mute(False)
                    # If paused, keep paused state; if playing, ensure volume is set
                    if self.is_playing:
                        self.player.audio_set_volume(int(self.volume * 100))
            except Exception:
                pass
            self._load_video_stream()
            self._start_video_sync_timer()
            # Remember play state to guide initial sync
            self._audio_was_playing_before_video = bool(self.is_playing)
        except Exception as e:
            print(f"Error showing video modal: {e}")

    def _hide_video_modal(self):
        self.video_visible = False
        self.video_toggle_btn.configure(text="▲")
        # Stop sync timer
        if self._video_sync_job:
            try:
                self.after_cancel(self._video_sync_job)
            except Exception:
                pass
            self._video_sync_job = None
        # Release video resources
        try:
            if self.video_player:
                self.video_player.stop()
                try:
                    self.video_player.release()
                except Exception:
                    pass
            self.video_player = None
            if self.video_vlc_instance:
                try:
                    self.video_vlc_instance.release()
                except Exception:
                    pass
            self.video_vlc_instance = None
        except Exception:
            pass
        # Destroy overlay
        try:
            if self.video_window and self.video_window.winfo_exists():
                self.video_window.destroy()
            self.video_window = None
        except Exception:
            pass
        # Unbind root handler
        try:
            if self._root_configure_bind_id:
                self.winfo_toplevel().unbind("<Configure>", self._root_configure_bind_id)
                self._root_configure_bind_id = None
        except Exception:
            pass

    def _position_video_modal(self):
        """Position the overlay to cover the area above the player inside the app window."""
        if not (self.video_window and self.video_window.winfo_exists()):
            return
        root = self.winfo_toplevel()
        try:
            root.update_idletasks()
            root_x = root.winfo_rootx()
            root_y = root.winfo_rooty()
            root_w = root.winfo_width()
            player_top_y = self.winfo_rooty()
            height = max(100, player_top_y - root_y)
            self.video_window.geometry(f"{root_w}x{height}+{root_x}+{root_y}")
        except Exception:
            pass

    def _get_video_url(self):
        """Resolve the video URL for the current track.
        Specifically targets 1920x1080 MP4 with AV1 codec.
        """
        try:
            video_id = self.song_data.get('videoId')
            if not video_id:
                return None
                
            youtube_url = f"https://www.youtube.com/watch?v={video_id}"
            
            # Set up yt-dlp options
            ydl_opts = {
                'quiet': True,
                'no_warnings': False,
                'extract_flat': False,
                'ignoreerrors': True,
                'noplaylist': True,
                'socket_timeout': 30,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                },
                # Target specific format: 1920x1080 MP4 with AV1 codec
                'format': 'bestvideo[width=1920][height=1080][vcodec^=av01][ext=mp4]+bestaudio[ext=m4a]/best[width=1920][height=1080][ext=mp4]/best',
                'merge_output_format': 'mp4',
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    info = ydl.extract_info(youtube_url, download=False)
                    if not info:
                        raise Exception("No video info returned")
                        
                    if 'url' in info:
                        print(f"Selected format: {info.get('format')}")
                        return info['url']
                    
                    # If direct URL not found, try to find in formats
                    formats = info.get('formats', [])
                    for f in formats:
                        if (f.get('width') == 1920 and 
                            f.get('height') == 1080 and 
                            f.get('vcodec', '').startswith('av01') and 
                            f.get('ext') == 'mp4' and 
                            f.get('url')):
                            print(f"Found matching format: {f.get('format_id')}")
                            return f['url']
                    
                    # Fallback to any 1080p format if exact match not found
                    for f in formats:
                        if (f.get('width') == 1920 and 
                            f.get('height') == 1080 and 
                            f.get('url')):
                            print(f"Falling back to 1080p format: {f.get('format_id')}")
                            return f['url']
                    
                    raise Exception("No suitable 1080p format found")
                    
                except Exception as e:
                    print(f"Error in format selection: {e}")
                    # Fallback to any available format if specific format not found
                    try:
                        ydl_opts['format'] = 'bestvideo[height<=?1080]+bestaudio/best'
                        info = ydl.extract_info(youtube_url, download=False)
                        if info and 'url' in info:
                            print("Falling back to best available format")
                            return info['url']
                    except Exception as fallback_error:
                        print(f"Fallback failed: {fallback_error}")
                    
                    return None
                    
        except Exception as e:
            print(f"Error getting video URL: {e}")
            return None

    def _load_video_stream(self):
        """Prepare the VLC video player with audio muted for the current song.
        Runs heavy work in a background thread to avoid UI jank.
        """
        if not self.video_visible:
            return
        
        def _prepare():
            try:
                video_url = self._get_video_url()
                if not video_url:
                    return
                # Create/refresh VLC instance and player
                if self.video_vlc_instance is None:
                    # Separate instance for video; keep audio enabled globally and mute per-media/player
                    self.video_vlc_instance = vlc.Instance('--intf', 'dummy')
                vp = self.video_vlc_instance.media_player_new()
                
                # Keep video silent; audio comes from the audio player
                vp.audio_set_mute(True)
                vp.audio_set_volume(0)
                
                vmedia = self.video_vlc_instance.media_new(video_url)
                # Add buffering/smoothness options to media
                try:
                    vmedia.add_option(":network-caching=1500")
                    vmedia.add_option(":clock-jitter=0")
                    vmedia.add_option(":drop-late-frames")
                    vmedia.add_option(":skip-frames")
                    # Ensure video media carries no audio to avoid any interference
                    vmedia.add_option(":no-audio")
                    # Prefer hardware decode on Windows 10+
                    vmedia.add_option(":avcodec-hw=d3d11va")
                except Exception:
                    pass
                vp.set_media(vmedia)

                def _attach_and_start():
                    if not (self.video_visible and self.video_window and self.video_window.winfo_exists()):
                        return
                    self.video_window.update_idletasks()
                    try:
                        vp.set_hwnd(self.video_frame.winfo_id())  # Windows
                    except Exception:
                        try:
                            vp.set_xwindow(self.video_frame.winfo_id())  # X11
                        except Exception:
                            pass
                    # Replace any previous player
                    old = getattr(self, 'video_player', None)
                    if old and old != vp:
                        try:
                            old.stop()
                            old.release()
                        except Exception:
                            pass
                    self.video_player = vp
                    vp.play()
                    # Ensure video stays silent after starting
                    try:
                        vp.audio_set_mute(True)
                        vp.audio_set_volume(0)
                    except Exception:
                        pass
                    # Re-ensure main audio is active and audible
                    try:
                        self._ensure_audio_active()
                    except Exception:
                        pass
                    # Give VLC a moment before applying pause/sync and force time
                    self.after(200, lambda: self._enforce_video_state(sync_time=True))

                self.after(0, _attach_and_start)
            except Exception as e:
                print(f"Error loading video stream: {e}")

        threading.Thread(target=_prepare, daemon=True).start()

    def _enforce_video_state(self, sync_time=False):
        """Ensure video play/pause matches audio state; optionally sync time."""
        try:
            if not self.video_player:
                return
            # Apply pause/play deterministically
            self.video_player.set_pause(not self.is_playing)
            if sync_time:
                self._sync_video_once()
            # Always ensure main audio stays unmuted when video overlay exists
            try:
                if self.video_visible and self.player:
                    self.player.audio_set_mute(False)
                    self.player.audio_set_volume(int(self.volume * 100))
            except Exception:
                pass
        except Exception:
            pass

    def _sync_video_once(self):
        """One-time sync of video player's time/state to the audio player."""
        try:
            if not (self.player and self.video_player):
                return
            at_ms = int(self.player.get_time())
            vt_ms = int(self.video_player.get_time())
            drift = at_ms - vt_ms
            
            # Only sync if drift is significant (more than 1 second)
            if abs(drift) > 1000:  # Increased from 600ms to 1000ms
                self.video_player.set_time(max(0, at_ms))
        except Exception as e:
            print(f"Sync error: {e}")

    def _start_video_sync_timer(self):
        """Continuously align video with audio and keep overlay positioned."""
        def _tick():
            if not self.video_visible:
                return
                
            self._position_video_modal()
            
            try:
                if not (self.video_player and self.player):
                    return
                    
                # Enforce play/pause state
                self._enforce_video_state(sync_time=False)
                
                # Only sync time every 2 seconds to reduce jitter
                current_time = time.time()
                if not hasattr(self, '_last_sync_time'):
                    self._last_sync_time = current_time
                    
                if current_time - self._last_sync_time >= 2.0:  # Sync every 2 seconds
                    self._last_sync_time = current_time
                    
                    # Get current positions
                    at_ms = int(self.player.get_time())
                    vt_ms = int(self.video_player.get_time())
                    drift = at_ms - vt_ms
                    
                    # Only adjust if drift is significant (more than 1.5 seconds)
                    if abs(drift) > 1500:
                        self.video_player.set_time(max(0, at_ms))
                    
                    # Remove rate adjustments to prevent stuttering
                    try:
                        self.video_player.set_rate(1.0)
                    except Exception:
                        pass
                        
            except Exception as e:
                print(f"Sync tick error: {e}")
                
            # Schedule next tick (slightly reduced frequency)
            if self.video_visible:
                self._video_sync_job = self.after(400, _tick)  # Increased from 300ms to 400ms
                
        _tick()
    
    def _toggle_shuffle(self):
        """Toggle shuffle mode and create shuffled playlist"""
        import random
        
        self.shuffle_enabled = not self.shuffle_enabled
        
        if self.shuffle_enabled:
            # Create shuffled playlist excluding current song
            current_song = self.playlist[self.current_index]
            other_songs = [song for i, song in enumerate(self.playlist) if i != self.current_index]
            
            # Shuffle the other songs
            random.shuffle(other_songs)
            
            # Create new shuffled playlist: current song first, then shuffled others
            self.shuffled_playlist = [current_song] + other_songs
            self.shuffled_index = 0  # Start at current song
            
            self.shuffle_btn.configure(fg_color="#1DB954", hover_color="#1ed760")
            print("Shuffle enabled - playlist shuffled")
        else:
            # Reset to original playlist
            self.shuffled_playlist = None
            self.shuffled_index = 0
            self.shuffle_btn.configure(fg_color="#333333", hover_color="#444444")
            print("Shuffle disabled - using original playlist")

    def _toggle_repeat(self):
        self.repeat_enabled = not self.repeat_enabled
        if self.repeat_enabled:
            self.repeat_btn.configure(fg_color="#1DB954", hover_color="#1ed760")
        else:
            self.repeat_btn.configure(fg_color="#333333", hover_color="#444444")

    def _get_next_song_index(self):
        """Get the next song index based on shuffle state"""
        if self.shuffle_enabled and self.shuffled_playlist:
            # Use shuffled playlist
            if self.shuffled_index < len(self.shuffled_playlist) - 1:
                return self.shuffled_index + 1
            else:
                return None  # End of shuffled playlist
        else:
            # Use original playlist
            if self.current_index < len(self.playlist) - 1:
                return self.current_index + 1
            else:
                return None  # End of original playlist

    def _get_previous_song_index(self):
        """Get the previous song index based on shuffle state"""
        if self.shuffle_enabled and self.shuffled_playlist:
            # Use shuffled playlist
            if self.shuffled_index > 0:
                return self.shuffled_index - 1
            else:
                return None  # Beginning of shuffled playlist
        else:
            # Use original playlist
            if self.current_index > 0:
                return self.current_index - 1
            else:
                return None  # Beginning of original playlist

    def _next_song(self):
        """Go to the next song in the playlist (shuffled or original)"""
        next_index = self._get_next_song_index()
        
        if next_index is not None:
            if self.shuffle_enabled and self.shuffled_playlist:
                # Use shuffled playlist
                self.shuffled_index = next_index
                self.song_data = self.shuffled_playlist[self.shuffled_index]
                # Find corresponding index in original playlist for callback
                original_index = self.playlist.index(self.song_data)
                self.current_index = original_index
            else:
                # Use original playlist
                self.current_index = next_index
                self.song_data = self.playlist[self.current_index]
            
            self._update_song_info()
            self._load_audio_stream()
            # If video overlay is visible, update video stream too
            if self.video_visible:
                self._load_video_stream()
            
            # Call callback if set
            if self.on_song_change:
                self.on_song_change(self.current_index, self.song_data)
        else:
            print("Already at the last song")

    def _previous_song(self):
        """Go to the previous song in the playlist (shuffled or original)"""
        prev_index = self._get_previous_song_index()
        
        if prev_index is not None:
            if self.shuffle_enabled and self.shuffled_playlist:
                # Use shuffled playlist
                self.shuffled_index = prev_index
                self.song_data = self.shuffled_playlist[self.shuffled_index]
                # Find corresponding index in original playlist for callback
                original_index = self.playlist.index(self.song_data)
                self.current_index = original_index
            else:
                # Use original playlist
                self.current_index = prev_index
                self.song_data = self.playlist[self.current_index]
            
            self._update_song_info()
            self._load_audio_stream()
            # If video overlay is visible, update video stream too
            if self.video_visible:
                self._load_video_stream()
            
            # Call callback if set
            if self.on_song_change:
                self.on_song_change(self.current_index, self.song_data)
        else:
            print("Already at the first song")
    
    def _on_volume_change(self, value):
        self.volume = value
        if self.player:
            # Set VLC volume (0-100)
            self.player.audio_set_volume(int(value * 100))
        print(f"Volume: {value}")
    
    def _update_progress(self):
        if self.player and self.is_playing:
            try:
                # Get current time from VLC player
                current_time = self.player.get_time() / 1000  # Convert to seconds
                if current_time > 0:
                    self.current_time = current_time
                    
                    if self.total_duration > 0:
                        progress = self.current_time / self.total_duration
                        self.progress_bar.set(progress)
                    
                    # Update time labels
                    current_min = int(self.current_time) // 60
                    current_sec = int(self.current_time) % 60
                    self.current_time_label.configure(text=f"{current_min}:{current_sec:02d}")
                    
                    # Update total time label
                    total_min = self.total_duration // 60
                    total_sec = self.total_duration % 60
                    self.total_time_label.configure(text=f"{total_min}:{total_sec:02d}")
                    
                    # Check if song ended
                    if self.player.get_state() == vlc.State.Ended:
                        self.is_playing = False
                        self.play_btn.configure(text="▶")
                        self.current_time = 0
                        self.progress_bar.set(0)
                        self.current_time_label.configure(text="0:00")
                        
                        # Repeat logic
                        if self.repeat_enabled:
                            print("Repeat enabled - replaying current song...")
                            self._load_audio_stream()
                        else:
                            # Auto-play next song if available
                            next_index = self._get_next_song_index()
                            if next_index is not None:
                                print("Song ended, playing next song...")
                                self._next_song()
                            else:
                                print("Song ended, reached end of playlist")
                            
            except Exception as e:
                print(f"Error updating progress: {e}")
        
        # Update every 500ms for smoother progress
        self.after(500, self._update_progress)
    
    def _on_progress_click(self, event):
        """Handle progress bar click for seeking"""
        if not self.player or not self.total_duration:
            return
            
        # Calculate click position as percentage
        progress_bar_width = self.progress_bar.winfo_width()
        click_x = event.x
        seek_percentage = click_x / progress_bar_width
        
        # Calculate seek time
        seek_time = int(seek_percentage * self.total_duration * 1000)  # Convert to milliseconds
        
        # Store current play state
        was_playing = self.is_playing
        
        # If paused, temporarily play to seek, then pause again
        if not was_playing:
            self.player.play()
            # Give VLC a moment to start
            self.after(50, lambda: self._perform_seek_and_pause(seek_time, seek_percentage))
        else:
            # If already playing, seek directly
            self.player.set_time(seek_time)
            self.current_time = seek_percentage * self.total_duration
            # Sync video to the new time
            self._enforce_video_state(sync_time=True)

    def _perform_seek_and_pause(self, seek_time, seek_percentage):
        """Helper method to seek when paused and then pause again"""
        try:
            # Perform the seek
            self.player.set_time(seek_time)
            self.current_time = seek_percentage * self.total_duration
            # Sync video time as well
            self._enforce_video_state(sync_time=True)
            
            # Pause again after seeking
            self.player.pause()
            
            # Update the progress bar to show the new position
            if self.total_duration > 0:
                progress = self.current_time / self.total_duration
                self.progress_bar.set(progress)
            
            # Update time labels
            current_min = int(self.current_time) // 60
            current_sec = int(self.current_time) % 60
            self.current_time_label.configure(text=f"{current_min}:{current_sec:02d}")
            
        except Exception as e:
            print(f"Error during seek: {e}")
    
    def _close_player(self):
        """Close the player and call the on_close callback"""
        if self.on_close:
            self.on_close()
        self.destroy()
    
    def destroy(self):
        """Clean up VLC resources when destroying the player"""
        # Ensure video modal and resources are cleaned up
        try:
            if getattr(self, 'video_visible', False):
                self._hide_video_modal()
        except Exception:
            pass
        if self.player:
            self.player.stop()
        if self.vlc_instance:
            self.vlc_instance.release()
        super().destroy()