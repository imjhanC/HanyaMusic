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
        self.volume = 0.7
        self.shuffle_enabled = False
        
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
        
        # Volume section (right) - horizontal layout
        self._create_volume_section()
    
    def _create_thumbnail_section(self):
        # Thumbnail container
        thumb_frame = ctk.CTkFrame(self, fg_color="transparent", width=100, height=100)
        thumb_frame.grid(row=0, column=0, padx=5, pady=10, sticky="nsw")
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
        
        # Center the buttons by using a grid layout
        buttons_frame.grid_columnconfigure(0, weight=1)
        buttons_frame.grid_columnconfigure(1, weight=0)
        buttons_frame.grid_columnconfigure(2, weight=0)
        buttons_frame.grid_columnconfigure(3, weight=0)
        buttons_frame.grid_columnconfigure(4, weight=0)
        buttons_frame.grid_columnconfigure(5, weight=1)
        
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
        self.prev_btn.grid(row=0, column=1, padx=5)
        
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
        self.play_btn.grid(row=0, column=2, padx=10)
        
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
        self.next_btn.grid(row=0, column=3, padx=5)
        
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
        self.shuffle_btn.grid(row=0, column=4, padx=(20, 0))
    
    def _create_volume_section(self):
        # Volume container - horizontal layout
        volume_frame = ctk.CTkFrame(self, fg_color="transparent")
        volume_frame.grid(row=0, column=2, padx=15, pady=20, sticky="nse")
        
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

        # Close button
        self.close_btn = ctk.CTkButton(
            volume_frame,
            text="✖",
            width=30,
            height=30,
            corner_radius=15,
            fg_color="#FF0000",
            hover_color="#FF3333",
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=16),
            command=self._close_player
        )
        self.close_btn.pack(side="right", padx=(10, 0))
    
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
        else:
            # Play
            self.player.play()
            self.play_btn.configure(text="⏸")
            self.is_playing = True
    
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

    def _perform_seek_and_pause(self, seek_time, seek_percentage):
        """Helper method to seek when paused and then pause again"""
        try:
            # Perform the seek
            self.player.set_time(seek_time)
            self.current_time = seek_percentage * self.total_duration
            
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
        if self.player:
            self.player.stop()
        if self.vlc_instance:
            self.vlc_instance.release()
        super().destroy()