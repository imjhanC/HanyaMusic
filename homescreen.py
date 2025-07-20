import customtkinter as ctk
from youtubesearchpython import VideosSearch
import webbrowser
from PIL import Image, ImageTk
import requests
from io import BytesIO
from functools import partial
import pygame
import threading
import time
import vlc
import yt_dlp

class HomeScreen(ctk.CTkFrame):
    def __init__(self, master, switch_to_main_callback=None, initial_search=None):
        super().__init__(master, fg_color="#121212")
        self.pack(fill="both", expand=True, padx=20, pady=20)
        self.thumbnail_refs = []  
        self.current_results = []  
        self.current_index = None  
        self.now_playing_bar = None
        self.is_playing = False
        self.current_time = 0
        self.update_thread = None
        self.stop_thread = False
        self.search_thread = None
        self.is_searching = False
        self.search_delay = 0.3  
        self.search_timer = None
        self.player_visible = False  
        self.switch_to_main_callback = switch_to_main_callback
        self.initial_search = initial_search
        # Initialize VLC player
        try:
            self.vlc_instance = vlc.Instance('--intf', 'dummy')
            self.player = self.vlc_instance.media_player_new()
            self.vlc_available = True
        except Exception as e:
            print(f"VLC not available: {e}")
            self.vlc_available = False
            self.player = None
        self.ydl_opts = {
            'format': 'bestaudio[abr>0]/bestaudio/best',
            'quiet': True,
            'no_warnings': True,
        }
        pygame.mixer.init()
        self.build_ui()
        if self.initial_search:
            self.search_var.set(self.initial_search)
            self.perform_search(self.initial_search)

    def build_ui(self):
        # Main container
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True)
        
        # Search bar container to center it
        search_container = ctk.CTkFrame(main_container, fg_color="transparent")
        search_container.pack(fill="x", pady=(10, 20))
        
        # Search bar centered
        search_frame = ctk.CTkFrame(search_container, fg_color="transparent")
        search_frame.pack(expand=True, anchor="center")
        
        self.search_var = ctk.StringVar()
        search_entry = ctk.CTkEntry(
            search_frame,
            textvariable=self.search_var,
            width=400,
            placeholder_text="Search for music..."
        )
        search_entry.pack(side="left", padx=(0, 10))
        search_entry.bind("<KeyRelease>", self._on_search_input)

        # Content area with scrollable frame and player bar
        content_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        content_frame.pack(fill="both", expand=True)
        
        # Scrollable results frame
        self.results_canvas = ctk.CTkCanvas(content_frame, bg="#121212", highlightthickness=0)
        self.scrollbar = ctk.CTkScrollbar(content_frame, orientation="vertical", command=self.results_canvas.yview)
        self.scrollable_frame = ctk.CTkFrame(self.results_canvas, fg_color="transparent")
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.results_canvas.configure(
                scrollregion=self.results_canvas.bbox("all")
            )
        )
        
        self.results_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.results_canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.results_canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Now Playing Bar (initially hidden)
        self.now_playing_bar = ctk.CTkFrame(
            content_frame,
            fg_color="#181818",
            height=100,
            corner_radius=12
        )
        self._build_now_playing_bar()
        
        self.bind("<Configure>", self._on_window_resize)
        self.results_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        self.results_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def _on_window_resize(self, event=None):
        if self.player_visible and self.now_playing_bar.winfo_exists():
            self.now_playing_bar.place(
                relx=0.5, 
                rely=1.0, 
                anchor="s", 
                relwidth=1.0, 
                y=-10
            )
            self.results_canvas.configure(height=self.winfo_height() - 180)

    def _build_now_playing_bar(self):
        if self.now_playing_bar is not None:
            for widget in self.now_playing_bar.winfo_children():
                widget.destroy()
        
        # Fonts
        try:
            title_font = ctk.CTkFont(family="SF Pro Display", size=16, weight="bold")
            artist_font = ctk.CTkFont(family="SF Pro Display", size=13)
            time_font = ctk.CTkFont(family="SF Pro Display", size=11)
            control_font = ctk.CTkFont(family="SF Pro Display", size=16)
            play_font = ctk.CTkFont(family="SF Pro Display", size=18)
        except:
            title_font = ctk.CTkFont(family="Helvetica", size=16, weight="bold")
            artist_font = ctk.CTkFont(family="Helvetica", size=13)
            time_font = ctk.CTkFont(family="Helvetica", size=11)
            control_font = ctk.CTkFont(family="Helvetica", size=16)
            play_font = ctk.CTkFont(family="Helvetica", size=18)
        
        self.now_playing_bar.configure(fg_color="#181818", border_width=1, border_color="#333333")
        
        content_frame = ctk.CTkFrame(self.now_playing_bar, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=20, pady=15)
        
        # Left section
        left_section = ctk.CTkFrame(content_frame, fg_color="transparent")
        left_section.pack(side="left", fill="y")
        
        thumbnail_container = ctk.CTkFrame(left_section, fg_color="#333333", width=80, height=80, corner_radius=10)
        thumbnail_container.pack(side="left", padx=(0, 20))
        thumbnail_container.pack_propagate(False)
        
        self.np_thumbnail = ctk.CTkLabel(thumbnail_container, text="", width=76, height=76)
        self.np_thumbnail.pack(expand=True, fill="both", padx=2, pady=2)
        
        info_frame = ctk.CTkFrame(left_section, fg_color="transparent")
        info_frame.pack(side="left", fill="y", expand=True)
        
        self.np_title = ctk.CTkLabel(
            info_frame,
            text="No song selected",
            font=title_font,
            text_color="#FFFFFF"
        )
        self.np_title.pack(anchor="w", pady=(5, 2))
        
        self.np_artist = ctk.CTkLabel(
            info_frame,
            text="",
            font=artist_font,
            text_color="#B3B3B3"
        )
        self.np_artist.pack(anchor="w")
        
        # Center section
        center_section = ctk.CTkFrame(content_frame, fg_color="transparent")
        center_section.pack(side="left", fill="both", expand=True, padx=20)
        
        progress_frame = ctk.CTkFrame(center_section, fg_color="transparent")
        progress_frame.pack(fill="x", pady=(10, 5))
        
        self.np_slider = ctk.CTkSlider(
            progress_frame,
            from_=0,
            to=100,
            progress_color="#1DB954",
            button_color="#1DB954",
            button_hover_color="#1ED760",
            command=self._on_slider_change
        )
        self.np_slider.pack(fill="x")
        
        time_frame = ctk.CTkFrame(progress_frame, fg_color="transparent")
        time_frame.pack(fill="x", pady=(5, 0))
        
        self.np_current_time = ctk.CTkLabel(
            time_frame,
            text="0:00",
            font=time_font,
            text_color="#B3B3B3"
        )
        self.np_current_time.pack(side="left")
        
        self.np_duration = ctk.CTkLabel(
            time_frame,
            text="0:00",
            font=time_font,
            text_color="#B3B3B3"
        )
        self.np_duration.pack(side="right")
        
        controls_frame = ctk.CTkFrame(center_section, fg_color="transparent")
        controls_frame.pack(pady=(5, 15))
        
        self.np_prev = ctk.CTkButton(
            controls_frame,
            text="⏮",
            width=38,
            height=38,
            fg_color="#282828",
            hover_color="#1DB954",
            text_color="#FFFFFF",
            font=control_font,
            corner_radius=19,
            command=self._on_prev
        )
        self.np_prev.grid(row=0, column=0, padx=4)
        
        self.np_play = ctk.CTkButton(
            controls_frame,
            text="▶",
            width=45,
            height=45,
            fg_color="#1DB954",
            hover_color="#1ED760",
            text_color="#FFFFFF",
            font=play_font,
            corner_radius=22,
            command=self._on_play_pause
        )
        self.np_play.grid(row=0, column=1, padx=6)
        
        self.np_next = ctk.CTkButton(
            controls_frame,
            text="⏭",
            width=38,
            height=38,
            fg_color="#282828",
            hover_color="#1DB954",
            text_color="#FFFFFF",
            font=control_font,
            corner_radius=19,
            command=self._on_next
        )
        self.np_next.grid(row=0, column=2, padx=4)
        
        # Volume control
        volume_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        volume_frame.pack(side="right", padx=(20, 0))
        
        volume_label = ctk.CTkLabel(
            volume_frame,
            text="🔊",
            font=ctk.CTkFont(size=14),
            text_color="#B3B3B3"
        )
        volume_label.pack(side="left", padx=(0, 8))
        
        self.volume_slider = ctk.CTkSlider(
            volume_frame,
            from_=0,
            to=100,
            width=80,
            progress_color="#1DB954",
            button_color="#1DB954",
            button_hover_color="#1ED760",
            command=self._on_volume_change
        )
        self.volume_slider.pack(side="left")
        self.volume_slider.set(70)

    def _show_player_bar(self):
        if not self.player_visible:
            self.player_visible = True
            self.now_playing_bar.place(
                relx=0.5,
                rely=1.0,
                anchor="s",
                relwidth=1.0,
                y=-10
            )
            self.results_canvas.configure(height=self.winfo_height() - 180)
            self.scrollable_frame.update_idletasks()
            self.results_canvas.configure(scrollregion=self.results_canvas.bbox("all"))

    def _hide_player_bar(self):
        if self.player_visible:
            self.player_visible = False
            self.now_playing_bar.place_forget()
            self.results_canvas.configure(height=0)
            self.scrollable_frame.update_idletasks()
            self.results_canvas.configure(scrollregion=self.results_canvas.bbox("all"))

    def _on_volume_change(self, value):
        volume = float(value) / 100.0
        if self.vlc_available and self.player:
            self.player.audio_set_volume(int(volume * 100))
        else:
            pygame.mixer.music.set_volume(volume)

    def _on_slider_change(self, value):
        if self.current_index is not None and self.vlc_available and self.player:
            total_seconds = self._duration_to_seconds(self.np_duration.cget("text"))
            if total_seconds > 0:
                position = float(value) / total_seconds
                self.player.set_position(position)
            self.current_time = float(value)
            self._update_time_display()

    def _show_now_playing(self, index):
        if not self.current_results or index < 0 or index >= len(self.current_results):
            return
            
        video = self.current_results[index]
        self.current_index = index
        title = video['title']
        duration = video.get('duration', '0:00')
        
        artist = "Unknown Artist"
        if " - " in title:
            artist, title = title.split(" - ", 1)
        
        total_seconds = self._duration_to_seconds(duration)
        
        self.np_title.configure(text=title[:35] + "..." if len(title) > 35 else title)
        self.np_artist.configure(text=artist[:35] + "..." if len(artist) > 35 else artist)
        self.np_duration.configure(text=duration)
        self.np_slider.configure(from_=0, to=total_seconds if total_seconds else 100)
        self.np_slider.set(0)
        self.np_current_time.configure(text="0:00")
        
        thumbnails = video.get('thumbnails', [])
        thumb_url = thumbnails[0]['url'] if thumbnails else None
        if thumb_url:
            thumb_img = self.fetch_thumbnail(thumb_url, size=(60, 60))
            if thumb_img:
                self.np_thumbnail.configure(image=thumb_img)
                self.thumbnail_refs.append(thumb_img)
        
        self._show_player_bar()
        self._play_audio(video['link'])

    def _play_audio(self, url):
        self._stop_audio()
        
        self.stop_thread = False
        self.is_playing = True
        self.update_thread = threading.Thread(target=self._audio_thread, args=(url,))
        self.update_thread.start()

    def _audio_thread(self, url):
        try:
            if self.vlc_available and self.player:
                try:
                    with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                        if info and 'url' in info:
                            stream_url = info['url']
                        else:
                            raise Exception("Could not extract stream URL")
                except Exception as e:
                    print(f"yt-dlp extraction error: {e}")
                    self._simulated_playback()
                    return
                
                try:
                    media = self.vlc_instance.media_new(stream_url)
                    self.player.set_media(media)
                except Exception as e:
                    print(f"VLC media creation error: {e}")
                    self._simulated_playback()
                    return
                
                self.player.play()
                time.sleep(2)
                
                self.is_playing = True
                self.current_time = 0
                
                self.master.after(0, lambda: self.np_play.configure(text="⏸"))
                
                # Use the new update loop
                self._vlc_update_loop()
            else:
                self._simulated_playback()
                
        except Exception as e:
            print(f"Audio playback error: {e}")

    def _simulated_playback(self):
        self.is_playing = True
        self.current_time = 0
        
        self.master.after(0, lambda: self.np_play.configure(text="⏸"))
        
        # Use the new update loop
        self._simulated_update_loop()

    def _update_time_display(self):
        if not hasattr(self, 'np_slider'):
            return
            
        self.np_slider.set(self.current_time)
        minutes = int(self.current_time // 60)
        seconds = int(self.current_time % 60)
        self.np_current_time.configure(text=f"{minutes}:{seconds:02d}")

    def _stop_audio(self):
        self.is_playing = False
        self.stop_thread = True
        if self.update_thread and self.update_thread.is_alive():
            self.update_thread.join()
        
        if self.vlc_available and self.player:
            self.player.stop()
        
        pygame.mixer.music.stop()

    def _on_play_pause(self):
        if self.current_index is None:
            return
            
        if self.is_playing:
            # Pausing
            self.is_playing = False
            self.stop_thread = True
            self.np_play.configure(text="▶")
            
            if self.vlc_available and self.player:
                self.player.pause()
            else:
                pygame.mixer.music.pause()
                
            # Wait for the update thread to finish
            if self.update_thread and self.update_thread.is_alive():
                self.update_thread.join()
        else:
            # Resuming
            self.is_playing = True
            self.stop_thread = False
            self.np_play.configure(text="⏸")
            
            if self.vlc_available and self.player:
                self.player.play()
                # Restart the update thread for VLC
                self.update_thread = threading.Thread(target=self._vlc_update_loop)
                self.update_thread.start()
            else:
                pygame.mixer.music.unpause()
                # Restart the update thread for simulated playback
                self.update_thread = threading.Thread(target=self._simulated_update_loop)
                self.update_thread.start()

    def _on_prev(self):
        if self.current_index is not None and self.current_index > 0:
            self._show_now_playing(self.current_index - 1)

    def _on_next(self):
        if self.current_index is not None and self.current_index < len(self.current_results) - 1:
            self._show_now_playing(self.current_index + 1)
        elif self.current_index is not None and self.current_index == len(self.current_results) - 1:
            self._show_now_playing(0)

    def _duration_to_seconds(self, duration):
        try:
            parts = list(map(int, duration.split(':')))
            if len(parts) == 3:
                return parts[0] * 3600 + parts[1] * 60 + parts[2]
            elif len(parts) == 2:
                return parts[0] * 60 + parts[1]
            elif len(parts) == 1:
                return parts[0]
        except:
            return 0
        return 0

    def fetch_thumbnail(self, url, size=(120, 68)):
        try:
            response = requests.get(url, timeout=5)
            img = Image.open(BytesIO(response.content))
            img.thumbnail(size, Image.Resampling.LANCZOS)
            return ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
        except Exception as e:
            print(f"Thumbnail fetch error: {e}")
            return None

    def _on_search_input(self, event=None):
        query = self.search_var.get().strip()
        if hasattr(self, 'search_timer') and self.search_timer:
            self.after_cancel(self.search_timer)
        if not query:
            for widget in self.scrollable_frame.winfo_children():
                widget.destroy()
            if self.switch_to_main_callback:
                self.switch_to_main_callback()
            return
        self.search_timer = self.after(800, lambda: self.perform_search(query))

    def perform_search(self, query=None):
        if query is None:
            query = self.search_var.get().strip()
            
        if not query:
            return
            
        if self.is_searching:
            return
            
        self.is_searching = True
        
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
            
        loading_label = ctk.CTkLabel(
            self.scrollable_frame,
            text="Searching...",
            font=("Helvetica", 14),
            text_color="#B3B3B3"
        )
        loading_label.pack(pady=20)
        
        self.search_thread = threading.Thread(target=self._search_thread, args=(query,))
        self.search_thread.daemon = True
        self.search_thread.start()

    def _search_thread(self, query):
        try:
            videos_search = VideosSearch(query, limit=1000)
            search_result = videos_search.result()
            if isinstance(search_result, dict):
                results = search_result.get('result', [])
            else:
                results = []
                
            self.master.after(0, self._display_search_results, results)
            
        except Exception as e:
            print(f"Search error: {e}")
            self.master.after(0, self._search_failed)
        finally:
            self.master.after(0, self._search_completed)

    def _display_search_results(self, results):
        self.current_results = results
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        # Create a container to center the cards
        container = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=10)

        for idx, video in enumerate(results):
            title = video['title']
            duration = video.get('duration', 'N/A')
            link = video['link']
            thumbnails = video.get('thumbnails', [])
            thumb_url = thumbnails[0]['url'] if thumbnails else None

            # Main card container - centered with max width
            card_container = ctk.CTkFrame(container, fg_color="transparent")
            card_container.pack(fill="x", pady=4)
            
            # Actual card with fixed max width and centered
            card = ctk.CTkFrame(card_container, fg_color="#181818", corner_radius=8, width= 1800, height=90) # 
            card.pack(anchor="center", pady=0, padx=20)  # Center the card
            card.pack_propagate(False)  # Maintain fixed size

            # Inner content frame with proper padding
            content_frame = ctk.CTkFrame(card, fg_color="transparent")
            content_frame.pack(fill="both", expand=True, padx=15, pady=10)

            # Thumbnail on the left
            thumbnail_frame = ctk.CTkFrame(content_frame, fg_color="#333333", width=70, height=70, corner_radius=6)
            thumbnail_frame.pack(side="left", padx=(0, 15))
            thumbnail_frame.pack_propagate(False)
            
            if thumb_url:
                placeholder = ctk.CTkLabel(thumbnail_frame, text="🔄", width=70, height=70)
                placeholder.pack(expand=True, fill="both")
                threading.Thread(target=self._load_thumbnail_async, args=(thumbnail_frame, thumb_url, idx)).start()
            else:
                placeholder = ctk.CTkLabel(thumbnail_frame, text="🎵", width=70, height=70)
                placeholder.pack(expand=True, fill="both")

            # Song info in the middle - better alignment
            info_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
            info_frame.pack(side="left", fill="both", expand=True, padx=(0, 15))

            # Title with better wrapping and centering
            title_label = ctk.CTkLabel(
                info_frame,
                text=title if len(title) <= 60 else title[:57] + "...",
                text_color="#FFFFFF",
                font=("Helvetica", 14, "bold"),
                cursor="hand2",
                anchor="w",
                justify="left"
            )
            title_label.pack(fill="x", pady=(8, 2))
            title_label.bind("<Button-1>", partial(self._on_result_click, idx))

            duration_label = ctk.CTkLabel(
                info_frame,
                text=f"Duration: {duration}",
                text_color="#B3B3B3",
                font=("Helvetica", 11),
                anchor="w",
                justify="left"
            )
            duration_label.pack(fill="x", pady=(0, 8))

            # Play button on the right - better positioning
            play_btn = ctk.CTkButton(
                content_frame,
                text="▶",
                width=50,
                height=50,
                fg_color="#1DB954",
                hover_color="#1ED760",
                text_color="#FFFFFF",
                font=("Helvetica", 16),
                corner_radius=25,
                command=partial(self._on_result_click, idx)
            )
            play_btn.pack(side="right", pady=10)

            # Hover effects
            def on_enter(e, c=card):
                c.configure(fg_color="#232323")
            def on_leave(e, c=card):
                c.configure(fg_color="#181818")
            
            card.bind("<Enter>", on_enter)
            card.bind("<Leave>", on_leave)
            
            # Make the entire card clickable
            def make_clickable(widget, index=idx):
                widget.bind("<Button-1>", partial(self._on_result_click, index))
                for child in widget.winfo_children():
                    if not isinstance(child, ctk.CTkButton):  # Don't override button clicks
                        make_clickable(child, index)
            
            make_clickable(card)

        self.scrollable_frame.update_idletasks()
        self.results_canvas.configure(scrollregion=self.results_canvas.bbox("all"))

    def _vlc_update_loop(self):
        """Separate update loop for VLC playback"""
        total_seconds = self._duration_to_seconds(self.np_duration.cget("text"))
        
        while self.is_playing and not self.stop_thread:
            try:
                if self.vlc_available and self.player:
                    state = self.player.get_state()
                    if str(state) == "State.Ended" or state == 6:
                        self.master.after(0, self._on_next)
                        break
                    
                    if total_seconds > 0:
                        position = self.player.get_position()
                        self.current_time = position * total_seconds
                        self.master.after(0, self._update_time_display)
                
                time.sleep(1)
            except Exception as e:
                print(f"VLC update error: {e}")
                break

    def _simulated_update_loop(self):
        """Separate update loop for simulated playback"""
        total_seconds = self._duration_to_seconds(self.np_duration.cget("text"))
        
        while self.is_playing and self.current_time < total_seconds and not self.stop_thread:
            time.sleep(1)
            if self.is_playing:
                self.current_time += 1
                self.master.after(0, self._update_time_display)
        
        if self.current_time >= total_seconds and not self.stop_thread and self.is_playing:
            self.master.after(0, self._on_next)

    def _load_thumbnail_async(self, thumbnail_frame, thumb_url, idx):
        try:
            thumb_img = self.fetch_thumbnail(thumb_url)
            if thumb_img:
                self.master.after(0, self._update_thumbnail, thumbnail_frame, thumb_img)
        except Exception as e:
            print(f"Thumbnail loading error: {e}")

    def _update_thumbnail(self, thumbnail_frame, thumb_img):
        try:
            for widget in thumbnail_frame.winfo_children():
                if isinstance(widget, ctk.CTkLabel) and (widget.cget("text") == "🔄" or widget.cget("text") == "🎵"):
                    widget.configure(image=thumb_img, text="")
                    self.thumbnail_refs.append(thumb_img)
                    break
        except Exception as e:
            print(f"Thumbnail update error: {e}")

    def _search_failed(self):
        error_label = ctk.CTkLabel(
            self.scrollable_frame,
            text="❌ Search failed. Please try again.",
            font=("Helvetica", 14),
            text_color="#FF6B6B"
        )
        error_label.pack(pady=20)

    def _search_completed(self):
        self.is_searching = False

    def _on_result_click(self, idx, event=None):
        self._show_now_playing(idx)

    def open_url(self, url):
        webbrowser.open(url)