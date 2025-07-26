import customtkinter as ctk
from youtubesearchpython import VideosSearch
import webbrowser
from PIL import Image
import requests
from io import BytesIO
from functools import partial
import threading

class HomeScreen(ctk.CTkFrame):
    def __init__(self, master, switch_to_main_callback=None, initial_search=None, player=None):
        super().__init__(master, fg_color="#121212")
        self.pack(fill="both", expand=True, padx=0, pady=0)
        self.thumbnail_refs = []  
        self.current_results = []  
        self.search_thread = None
        self.is_searching = False
        self.search_timer = None
        self.switch_to_main_callback = switch_to_main_callback
        self.initial_search = initial_search
        self.player = player
        self.build_ui()
        if self.initial_search:
            self.search_var.set(self.initial_search)
            self.perform_search(self.initial_search)

    def build_ui(self):
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True)
        
        search_container = ctk.CTkFrame(main_container, fg_color="transparent")
        search_container.pack(fill="x", pady=(10, 20))
        
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

        content_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        content_frame.pack(fill="both", expand=True)
        
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
        self.results_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        self.results_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

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

        container = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=10)

        for idx, video in enumerate(results):
            title = video['title']
            duration = video.get('duration', 'N/A')
            thumbnails = video.get('thumbnails', [])
            thumb_url = thumbnails[0]['url'] if thumbnails else None

            card_container = ctk.CTkFrame(container, fg_color="transparent")
            card_container.pack(fill="x", pady=4)
            
            card = ctk.CTkFrame(card_container, fg_color="#181818", corner_radius=8, width= 1800, height=90)
            card.pack(anchor="center", pady=0, padx=20)
            card.pack_propagate(False)

            content_frame_card = ctk.CTkFrame(card, fg_color="transparent")
            content_frame_card.pack(fill="both", expand=True, padx=15, pady=10)

            thumbnail_frame = ctk.CTkFrame(content_frame_card, fg_color="#333333", width=70, height=70, corner_radius=6)
            thumbnail_frame.pack(side="left", padx=(0, 15))
            thumbnail_frame.pack_propagate(False)
            
            if thumb_url:
                placeholder = ctk.CTkLabel(thumbnail_frame, text="🔄", width=70, height=70)
                placeholder.pack(expand=True, fill="both")
                threading.Thread(target=self._load_thumbnail_async, args=(thumbnail_frame, thumb_url)).start()
            else:
                placeholder = ctk.CTkLabel(thumbnail_frame, text="🎵", width=70, height=70)
                placeholder.pack(expand=True, fill="both")

            info_frame = ctk.CTkFrame(content_frame_card, fg_color="transparent")
            info_frame.pack(side="left", fill="both", expand=True, padx=(0, 15))

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

            play_btn = ctk.CTkButton(
                content_frame_card,
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

            def on_enter(e, c=card): c.configure(fg_color="#232323")
            def on_leave(e, c=card): c.configure(fg_color="#181818")
            
            card.bind("<Enter>", on_enter)
            card.bind("<Leave>", on_leave)
            
            def make_clickable(widget, index=idx):
                widget.bind("<Button-1>", partial(self._on_result_click, index))
                for child in widget.winfo_children():
                    if not isinstance(child, ctk.CTkButton):
                        make_clickable(child, index)
            
            make_clickable(card)

        self.scrollable_frame.update_idletasks()
        self.results_canvas.configure(scrollregion=self.results_canvas.bbox("all"))

    def _load_thumbnail_async(self, thumbnail_frame, thumb_url):
        try:
            thumb_img = self.fetch_thumbnail(thumb_url)
            if thumb_img:
                self.master.after(0, self._update_thumbnail, thumbnail_frame, thumb_img)
        except Exception as e:
            print(f"Thumbnail loading error: {e}")

    def _update_thumbnail(self, thumbnail_frame, thumb_img):
        try:
            for widget in thumbnail_frame.winfo_children():
                if isinstance(widget, ctk.CTkLabel):
                    widget.configure(image=thumb_img, text="")
                    self.thumbnail_refs.append(thumb_img)
                    break
        except Exception as e:
            print(f"Thumbnail update error: {e}")

    def _search_failed(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
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
        if self.player:
            self.player.play_song(self.current_results, idx)

    def open_url(self, url):
        webbrowser.open(url)