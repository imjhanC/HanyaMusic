import customtkinter as ctk
from PIL import Image, ImageTk
import requests
from io import BytesIO
import threading
from playerClass import MusicPlayerContainer

class SearchScreen(ctk.CTkFrame):
    def __init__(self, parent, results, load_more_callback=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.results = results
        self.load_more_callback = load_more_callback
        self.loading_more = False
        self.no_more_results = False
        self.configure(fg_color="transparent")
        
        # Track window resize state
        self._resize_in_progress = False
        self._resize_after_id = None
        
        # Music player container
        self.music_player = None
        
        # Main container frame that fills the window
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Configure grid weights for main container
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)
        
        # Create a frame to hold the canvas and scrollbar
        self.canvas_container = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.canvas_container.grid(row=0, column=0, sticky="nsew")
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
        self.canvas.bind('<Enter>', self._check_scroll_end)
        
        # Initialize cards list
        self.cards = []
        self.create_results_grid()
    
    def _show_music_player(self, song_data):
        # Remove existing player if any
        if self.music_player:
            self.music_player.destroy()
        
        # Create playlist from current results
        playlist = self.results
        
        # Find the index of the current song
        current_index = 0
        for i, result in enumerate(playlist):
            if result.get('videoId') == song_data.get('videoId'):
                current_index = i
                break
        
        # Create new music player with playlist
        self.music_player = MusicPlayerContainer(self, song_data, playlist, current_index)
        
        # Set callback for song changes
        self.music_player.set_on_song_change_callback(self._on_song_change)
        
        self.music_player.pack(side="bottom", fill="x", padx=5, pady=5)
        
        # Update canvas scroll region to account for player
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    
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
        self._check_scroll_end(event)

    def _check_scroll_end(self, event=None):
        # Only trigger if not already loading and not exhausted
        if self.loading_more or self.no_more_results or not self.load_more_callback:
            return
        # Get current scroll position
        try:
            first, last = self.canvas.yview()
            # If near the bottom (last > 0.98), trigger load more
            if last > 0.98:
                self.loading_more = True
                self._show_loading_more()
                self.load_more_callback(self._on_more_results)
        except Exception:
            pass

    def _show_loading_more(self):
        # Add a loading label at the end
        self.loading_label = ctk.CTkLabel(self.scrollable_frame, text="Loading more...", font=ctk.CTkFont(size=14))
        self.loading_label.grid(row=len(self.cards)*2, column=0, sticky="ew", padx=20, pady=10)
        self.scrollable_frame.update_idletasks()

    def _hide_loading_more(self):
        if hasattr(self, 'loading_label') and self.loading_label:
            self.loading_label.destroy()
            self.loading_label = None

    def _on_more_results(self, new_results):
        self._hide_loading_more()
        self.loading_more = False
        if not new_results:
            self.no_more_results = True
            # Optionally show a message at the end
            end_label = ctk.CTkLabel(self.scrollable_frame, text="No more results.", font=ctk.CTkFont(size=14), text_color="gray")
            end_label.grid(row=len(self.cards)*2, column=0, sticky="ew", padx=20, pady=10)
            return
        self.append_results(new_results)

    def create_results_grid(self):
        # Configure grid for scrollable frame
        self.scrollable_frame.columnconfigure(0, weight=1)
        for idx, result in enumerate(self.results):
            self._add_card(result, idx)

    def append_results(self, new_results):
        start_idx = len(self.cards)
        for i, result in enumerate(new_results):
            self._add_card(result, start_idx + i)
        self.scrollable_frame.update_idletasks()

    def _add_card(self, result, idx):
        # Create main card frame with dynamic width
        card = ctk.CTkFrame(
            self.scrollable_frame,
            fg_color="#222222",
            corner_radius=10,
            height=100
        )
        
        # Store card reference
        card._title = None  # Will store the title widget reference
        
        # Configure grid for the card to take full width
        card.grid(row=idx*2, column=0, sticky="nsew", padx=15, pady=5)
        card.grid_columnconfigure(1, weight=1)  # Make the content area expandable
        card.grid_columnconfigure(2, weight=0, minsize=70)  # Make the button column just wide enough
        
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
                response = requests.get(result['thumbnail_url'], timeout=5)
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
            text=result['title'],
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
        if 'uploader' in result and result['uploader']:
            details.append(result['uploader'])
        if 'duration' in result and result['duration']:
            details.append(result['duration'])
        if 'view_count' in result and result['view_count']:
            details.append(result['view_count'])
            
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
            command=lambda: self._show_music_player(result)
        )
        play_btn.grid(row=0, column=2, rowspan=2, padx=(0, 15), pady=15, sticky="nsew")
        
        # Add a separator between items
        if idx < len(self.results) - 1 or idx < len(self.cards) + len(self.results) - 1:
            separator = ctk.CTkFrame(
                self.scrollable_frame,
                height=1,
                fg_color="#333333"
            )
            separator.grid(row=idx*2 + 1, column=0, sticky="ew", padx=20, pady=2)
        
        self.cards.append(card)
        
        # Store videoId for deduplication
        if not hasattr(self, '_video_ids'):
            self._video_ids = set()
        self._video_ids.add(result.get('videoId'))
        
        # Update wraplength on window resize
        def update_wraplength(event):
            # Calculate available width for the title (total width - thumbnail - play button - paddings)
            available_width = max(100, card.winfo_width() - 220)  # 220 = thumbnail(120) + play button(50) + paddings(50)
            title.configure(wraplength=available_width)
            
        # Bind to card resize
        card.bind('<Configure>', update_wraplength)
        
    def get_all_video_ids(self):
        # Return all video IDs currently shown
        if hasattr(self, '_video_ids'):
            return list(self._video_ids)
        return []

    def _on_song_change(self, index, song_data):
        """Callback when song changes in the player"""
        print(f"Now playing: {song_data.get('title', 'Unknown Title')} (index: {index})")
        # You can add additional logic here, like updating the UI to highlight the current song