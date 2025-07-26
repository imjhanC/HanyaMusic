import customtkinter as ctk
from PIL import Image
import requests
from io import BytesIO
import pygame
import threading
import time
import vlc
import yt_dlp

class Player(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="#181818", height=100, corner_radius=12)
        self.master = master
        self.thumbnail_refs = []
        self.current_results = []
        self.current_index = None
        self.is_playing = False
        self.current_time = 0
        self.update_thread = None
        self.stop_thread = False
        self.player_visible = False

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
        self._build_now_playing_bar()
        self.hide_player()

    def _build_now_playing_bar(self):
        for widget in self.winfo_children():
            widget.destroy()

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

        self.configure(fg_color="#181818", border_width=1, border_color="#333333")

        content_frame = ctk.CTkFrame(self, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=20, pady=15)

        left_section = ctk.CTkFrame(content_frame, fg_color="transparent")
        left_section.pack(side="left", fill="y")

        thumbnail_container = ctk.CTkFrame(left_section, fg_color="#333333", width=80, height=80, corner_radius=10)
        thumbnail_container.pack(side="left", padx=(0, 20))
        thumbnail_container.pack_propagate(False)

        self.np_thumbnail = ctk.CTkLabel(thumbnail_container, text="", width=76, height=76)
        self.np_thumbnail.pack(expand=True, fill="both", padx=2, pady=2)

        info_frame = ctk.CTkFrame(left_section, fg_color="transparent")
        info_frame.pack(side="left", fill="y", expand=True)

        self.np_title = ctk.CTkLabel(info_frame, text="No song selected", font=title_font, text_color="#FFFFFF")
        self.np_title.pack(anchor="w", pady=(5, 2))

        self.np_artist = ctk.CTkLabel(info_frame, text="", font=artist_font, text_color="#B3B3B3")
        self.np_artist.pack(anchor="w")

        center_section = ctk.CTkFrame(content_frame, fg_color="transparent")
        center_section.pack(side="left", fill="both", expand=True, padx=20)

        progress_frame = ctk.CTkFrame(center_section, fg_color="transparent")
        progress_frame.pack(fill="x", pady=(10, 5))

        self.np_slider = ctk.CTkSlider(progress_frame, from_=0, to=100, progress_color="#1DB954", button_color="#1DB954", button_hover_color="#1ED760", command=self._on_slider_change)
        self.np_slider.pack(fill="x")

        time_frame = ctk.CTkFrame(progress_frame, fg_color="transparent")
        time_frame.pack(fill="x", pady=(5, 0))

        self.np_current_time = ctk.CTkLabel(time_frame, text="0:00", font=time_font, text_color="#B3B3B3")
        self.np_current_time.pack(side="left")

        self.np_duration = ctk.CTkLabel(time_frame, text="0:00", font=time_font, text_color="#B3B3B3")
        self.np_duration.pack(side="right")

        controls_frame = ctk.CTkFrame(center_section, fg_color="transparent")
        controls_frame.pack(pady=(5, 15))

        self.np_prev = ctk.CTkButton(controls_frame, text="⏮", width=38, height=38, fg_color="#282828", hover_color="#1DB954", text_color="#FFFFFF", font=control_font, corner_radius=19, command=self._on_prev)
        self.np_prev.grid(row=0, column=0, padx=4)

        self.np_play = ctk.CTkButton(controls_frame, text="▶", width=45, height=45, fg_color="#1DB954", hover_color="#1ED760", text_color="#FFFFFF", font=play_font, corner_radius=22, command=self._on_play_pause)
        self.np_play.grid(row=0, column=1, padx=6)

        self.np_next = ctk.CTkButton(controls_frame, text="⏭", width=38, height=38, fg_color="#282828", hover_color="#1DB954", text_color="#FFFFFF", font=control_font, corner_radius=19, command=self._on_next)
        self.np_next.grid(row=0, column=2, padx=4)

        volume_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        volume_frame.pack(side="right", padx=(20, 0))

        volume_label = ctk.CTkLabel(volume_frame, text="🔊", font=ctk.CTkFont(size=14), text_color="#B3B3B3")
        volume_label.pack(side="left", padx=(0, 8))

        self.volume_slider = ctk.CTkSlider(volume_frame, from_=0, to=100, width=80, progress_color="#1DB954", button_color="#1DB954", button_hover_color="#1ED760", command=self._on_volume_change)
        self.volume_slider.pack(side="left")
        self.volume_slider.set(70)

    def show_player(self):
        if not self.player_visible:
            self.pack(side="bottom", fill="x", padx=10, pady=10)
            self.player_visible = True

    def hide_player(self):
        if self.player_visible:
            self.pack_forget()
            self.player_visible = False

    def play_song(self, results, index):
        self.current_results = results
        self._show_now_playing(index)

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

        self.show_player()
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
                        stream_url = info['url']
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
                self._vlc_update_loop()
            else:
                self._simulated_playback()
        except Exception as e:
            print(f"Audio playback error: {e}")

    def _simulated_playback(self):
        self.is_playing = True
        self.current_time = 0
        self.master.after(0, lambda: self.np_play.configure(text="⏸"))
        self._simulated_update_loop()

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
            self.is_playing = False
            self.stop_thread = True
            self.np_play.configure(text="▶")
            if self.vlc_available and self.player:
                self.player.pause()
            else:
                pygame.mixer.music.pause()
            if self.update_thread and self.update_thread.is_alive():
                self.update_thread.join()
        else:
            self.is_playing = True
            self.stop_thread = False
            self.np_play.configure(text="⏸")
            if self.vlc_available and self.player:
                self.player.play()
                self.update_thread = threading.Thread(target=self._vlc_update_loop)
                self.update_thread.start()
            else:
                pygame.mixer.music.unpause()
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

    def _update_time_display(self):
        if not hasattr(self, 'np_slider'):
            return
        self.np_slider.set(self.current_time)
        minutes = int(self.current_time // 60)
        seconds = int(self.current_time % 60)
        self.np_current_time.configure(text=f"{minutes}:{seconds:02d}")

    def _vlc_update_loop(self):
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
        total_seconds = self._duration_to_seconds(self.np_duration.cget("text"))
        while self.is_playing and self.current_time < total_seconds and not self.stop_thread:
            time.sleep(1)
            if self.is_playing:
                self.current_time += 1
                self.master.after(0, self._update_time_display)
        if self.current_time >= total_seconds and not self.stop_thread and self.is_playing:
            self.master.after(0, self._on_next)

    def _duration_to_seconds(self, duration):
        try:
            parts = list(map(int, duration.split(':')))
            if len(parts) == 3: return parts[0] * 3600 + parts[1] * 60 + parts[2]
            elif len(parts) == 2: return parts[0] * 60 + parts[1]
            elif len(parts) == 1: return parts[0]
        except: return 0
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