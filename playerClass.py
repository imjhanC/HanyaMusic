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
    def __init__(self, parent, song_data, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.song_data = song_data
        self.is_playing = False
        self.current_time = 0
        self.total_duration = 0
        self.volume = 0.7
        self.shuffle_enabled = False
        
        # VLC and audio setup
        self.vlc_instance = None
        self.player = None
        self.media = None
        self.stream_url = None
        
        # Initialize pygame mixer for better audio control
        pygame.mixer.init()
        
        # Configure the player container
        self.configure(fg_color="#222222", corner_radius=15, height=120)
        
        # Create the player layout
        self._create_player_layout()
        
        # Load and prepare the audio stream
        self._load_audio_stream()
        
        # Start progress update timer
        self._update_progress()
    
    def _load_audio_stream(self):
        """Load the audio stream URL using yt-dlp"""
        def load_stream_async():
            try:
                # Configure yt-dlp options for audio
                ydl_opts = {
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
                
                # Extract audio stream URL
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(youtube_url, download=False)
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
                
                print("Audio stream loaded successfully")
                
                # Auto-play the song once loaded
                def start_playback():
                    if self.player:
                        self.player.play()
                        self.is_playing = True
                        self.play_btn.configure(text="⏸")
                        print("Auto-playing song")
                
                # Schedule auto-play on main thread
                self.after(0, start_playback)
                
            except Exception as e:
                print(f"Error loading audio stream: {e}")
        
        # Load stream in background thread
        threading.Thread(target=load_stream_async, daemon=True).start()
    
    def _create_player_layout(self):
        # Main layout with 3 columns: thumbnail, controls, volume
        self.grid_columnconfigure(1, weight=1)
        
        # Thumbnail section (left)
        self._create_thumbnail_section()
        
        # Controls section (center)
        self._create_controls_section()
        
        # Volume section (right)
        self._create_volume_section()
    
    def _create_thumbnail_section(self):
        # Thumbnail container
        thumb_frame = ctk.CTkFrame(self, fg_color="transparent", width=80, height=80)
        thumb_frame.grid(row=0, column=0, padx=15, pady=20, sticky="nsw")
        thumb_frame.grid_propagate(False)
        
        # Thumbnail label
        self.thumbnail_label = ctk.CTkLabel(thumb_frame, text="")
        self.thumbnail_label.pack(expand=True, fill="both")
        
        # Load thumbnail
        self._load_thumbnail()
    
    def _create_controls_section(self):
        # Controls container
        controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        controls_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=10)
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
        self.prev_btn.pack(side="left", padx=(0, 10))
        
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
        self.play_btn.pack(side="left", padx=10)
        
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
        self.next_btn.pack(side="left", padx=(10, 0))
        
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
        self.shuffle_btn.pack(side="left", padx=(20, 0))
    
    def _create_volume_section(self):
        # Volume container
        volume_frame = ctk.CTkFrame(self, fg_color="transparent")
        volume_frame.grid(row=0, column=2, padx=15, pady=20, sticky="nse")
        
        # Volume icon
        volume_icon = ctk.CTkLabel(
            volume_frame,
            text="🔊",
            font=ctk.CTkFont(size=16)
        )
        volume_icon.pack(pady=(0, 5))
        
        # Volume slider
        self.volume_slider = ctk.CTkSlider(
            volume_frame,
            from_=0,
            to=1,
            number_of_steps=100,
            orientation="vertical",
            height=80,
            command=self._on_volume_change
        )
        self.volume_slider.set(self.volume)
        self.volume_slider.pack()
    
    def _load_thumbnail(self):
        def load_image_async():
            try:
                response = requests.get(self.song_data['thumbnail_url'], timeout=5)
                img = Image.open(BytesIO(response.content))
                img.thumbnail((80, 80), Image.Resampling.LANCZOS)
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
        else:
            # Play
            self.player.play()
            self.play_btn.configure(text="⏸")
            self.is_playing = True
    
    def _previous_song(self):
        # Placeholder for previous song functionality
        print("Previous song")
        # You can implement playlist functionality here
    
    def _next_song(self):
        # Placeholder for next song functionality
        print("Next song")
        # You can implement playlist functionality here
    
    def _toggle_shuffle(self):
        self.shuffle_enabled = not self.shuffle_enabled
        if self.shuffle_enabled:
            self.shuffle_btn.configure(fg_color="#1DB954", hover_color="#1ed760")
        else:
            self.shuffle_btn.configure(fg_color="#333333", hover_color="#444444")
    
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
        
        # Seek to the position
        self.player.set_time(seek_time)
        self.current_time = seek_percentage * self.total_duration
    
    def destroy(self):
        """Clean up VLC resources when destroying the player"""
        if self.player:
            self.player.stop()
        if self.vlc_instance:
            self.vlc_instance.release()
        super().destroy()
