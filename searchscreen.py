import customtkinter as ctk
from PIL import Image, ImageTk
import requests
from io import BytesIO
import threading

class SearchScreen(ctk.CTkFrame):
    def __init__(self, parent, results, load_more_callback=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.results = results
        self.load_more_callback = load_more_callback
        self.loading_more = False
        self.no_more_results = False
        self.configure(fg_color="transparent")
        
        # Main container frame
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=0, pady=0)  # Remove padding
        
        # Create scrollable canvas with proper expansion
        self.canvas = ctk.CTkCanvas(
            self.main_container, 
            bg="#1a1a1a",
            highlightthickness=0,
            width=parent.winfo_width()  # Set initial width
        )
        
        self.scrollbar = ctk.CTkScrollbar(
            self.main_container, 
            orientation="vertical", 
            command=self.canvas.yview
        )
        
        self.scrollable_frame = ctk.CTkFrame(
            self.canvas, 
            fg_color="transparent"
        )
        
        # Configure the canvas scrolling
        self.scrollable_frame.bind(
            "<Configure>",
            self._on_frame_configure
        )
        
        # Pack scrollbar first, then canvas
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True, padx=0, pady=0)
        
        # Create window in canvas for the scrollable frame
        self.canvas_window = self.canvas.create_window(
            (0, 0), 
            window=self.scrollable_frame, 
            anchor="nw",
            width=self.winfo_screenwidth()  # Set initial width
        )
        
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Bind events
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind('<Enter>', self._check_scroll_end)
        self.canvas.bind('<Configure>', self._check_scroll_end)
        self.scrollbar.bind('<ButtonRelease-1>', self._check_scroll_end)
        
        # Initialize cards list
        self.cards = []
        self.create_results_grid()
    
    def _on_frame_configure(self, event=None):
        """Update the canvas scroll region and window width"""
        # Update scroll region
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        # Update canvas window width to match canvas width
        canvas_width = self.canvas.winfo_width()
        if canvas_width > 1:  # Ensure we have a valid width
            self.canvas.itemconfig(self.canvas_window, width=canvas_width)
    
    def _on_canvas_configure(self, event):
        """Handle canvas resize"""
        if event.width > 1:  # Ensure we have a valid width
            self.canvas.itemconfig(self.canvas_window, width=event.width)
    
    def on_canvas_configure(self, event):
        # Update the scroll region
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        # Update the canvas window width to match canvas width
        self.canvas.itemconfig(self.canvas_window, width=event.width)

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
        # Create main card frame
        card = ctk.CTkFrame(
            self.scrollable_frame, 
            fg_color="#222222",
            corner_radius=10,
            height=100
        )
        
        # Configure grid weights for full width
        card.grid(row=idx*2, column=0, sticky="nsew", padx=15, pady=5)
        card.grid_columnconfigure(1, weight=1)  # Make the content area expandable
        
        # Thumbnail (fixed size)
        placeholder_img = Image.new("RGB", (120, 80), color="#444444")
        tk_placeholder = ctk.CTkImage(light_image=placeholder_img, dark_image=placeholder_img, size=(120, 80))
        
        # Create a container for the thumbnail to maintain aspect ratio
        thumb_container = ctk.CTkFrame(card, fg_color="transparent", width=120, height=80)
        thumb_container.grid(row=0, column=0, rowspan=2, padx=10, pady=10, sticky="nsw")
        thumb_container.pack_propagate(False)  # Prevent container from resizing
        
        thumb = ctk.CTkLabel(thumb_container, text="")
        thumb.pack(expand=True, fill="both")
        
        # Start async image loading
        def load_image_async():
            try:
                response = requests.get(result['thumbnail_url'], timeout=5)
                img = Image.open(BytesIO(response.content))
                img.thumbnail((120, 80), Image.Resampling.LANCZOS)
                tk_image = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                def update_image():
                    thumb.configure(image=tk_image)
                    thumb.image = tk_image
                self.after(0, update_image)
            except Exception as e:
                print(f"Error loading image: {e}")
        
        threading.Thread(target=load_image_async, daemon=True).start()
        
        # Content area (title, artist, etc.)
        content_frame = ctk.CTkFrame(card, fg_color="transparent")
        content_frame.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(0, 20), pady=10)
        content_frame.columnconfigure(0, weight=1)
        
        # Title
        title = ctk.CTkLabel(
            content_frame,
            text=result['title'],
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
            justify="left",
            wraplength=0  # Allow text to wrap naturally
        )
        title.grid(row=0, column=0, sticky="nsw", pady=(0, 5))
        
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
            width=50,
            height=50,
            corner_radius=25,
            fg_color="#1DB954",
            hover_color="#1ed760",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        play_btn.grid(row=0, column=2, rowspan=2, padx=15, pady=0, sticky="ns")
        
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

    def get_all_video_ids(self):
        # Return all video IDs currently shown
        if hasattr(self, '_video_ids'):
            return list(self._video_ids)
        return []