import customtkinter as ctk
from PIL import Image, ImageTk
import requests
from io import BytesIO
import threading
from playerClass import MusicPlayerContainer
from FirebaseClass import FirebaseManager

class SearchScreen(ctk.CTkFrame):
    def __init__(self, parent, results, load_more_callback=None, current_user=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.results = results
        self.load_more_callback = load_more_callback
        self.current_user = current_user
        self.firebase_manager = FirebaseManager() if current_user else None
        self.loading_more = False
        self.no_more_results = False
        self.configure(fg_color="transparent")
        
        # Track window resize state
        self._resize_in_progress = False
        self._resize_after_id = None
        
        # Song selection callback
        self.song_selection_callback = None
        
        # Add playlist callback
        self.add_to_playlist_callback = None
        
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
    
    def set_song_selection_callback(self, callback):
        """Set callback function to be called when a song is selected"""
        self.song_selection_callback = callback
    
    def set_add_to_playlist_callback(self, callback):
        """Set callback function to be called when adding song to playlist"""
        self.add_to_playlist_callback = callback
    
    def _on_song_selected(self, song_data):
        """Called when a song is selected from the search results"""
        if self.song_selection_callback:
            # Find the index of the selected song in the current results
            current_index = 0
            for i, result in enumerate(self.results):
                if result.get('videoId') == song_data.get('videoId'):
                    current_index = i
                    break
            
            # Call the callback with song data, playlist, and current index
            self.song_selection_callback(song_data, self.results, current_index)
    
    def _on_like_button_clicked(self, song_data, like_button):
        """Handle like button click"""
        if not self.current_user or not self.firebase_manager:
            print("User not logged in")
            return
        
        # Toggle like status
        success, is_liked, message = self.firebase_manager.toggle_song_like(self.current_user, song_data)
        
        if success and like_button:
            # Update button appearance with consistent sizing
            if is_liked:
                like_button.configure(
                    text="♥",
                    fg_color="#FF6B6B",
                    hover_color="#FF5252",
                    font=ctk.CTkFont(size=14)  # Smaller font for filled heart
                )
            else:
                like_button.configure(
                    text="♡",
                    fg_color="#333333",
                    hover_color="#444444",
                    font=ctk.CTkFont(size=16)  # Normal font for empty heart
                )
            print(message)
        else:
            print(f"Error: {message}")
    
    def _on_right_click(self, event, song_data):
        """Handle right-click on song card to show context menu"""
        if not self.current_user or not self.add_to_playlist_callback:
            return
        
        # Create context menu
        self._show_context_menu(event, song_data)
    
    def _show_context_menu(self, event, song_data):
        """Show context menu for adding song to playlist"""
        # Create floating menu frame
        self.context_menu = ctk.CTkFrame(
            self,
            width=250,
            corner_radius=10,
            fg_color="#2a2a2a",
            border_width=1,
            border_color="#444444"
        )
        
        # Get window dimensions
        window_width = self.winfo_width()
        window_height = self.winfo_height()
        menu_width = 250
        menu_height = 200  # Approximate height
        
        # Get cursor position relative to the window
        cursor_x = event.x
        cursor_y = event.y
        
        # Position menu to the right of cursor
        menu_x = cursor_x + 5
        menu_y = cursor_y
        
        # If not enough space on the right, position to the left
        if menu_x + menu_width > window_width:
            menu_x = cursor_x - menu_width - 5
        
        # Adjust vertical position if menu goes below window
        if menu_y + menu_height > window_height:
            menu_y = window_height - menu_height - 10
        
        # Ensure menu doesn't go above window
        if menu_y < 0:
            menu_y = 10
        
        self.context_menu.place(x=menu_x, y=menu_y)
        self.context_menu.lift()
        
        # Title
        title_label = ctk.CTkLabel(
            self.context_menu,
            text="Add to Playlist",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#FFFFFF"
        )
        title_label.pack(pady=(15, 5))
        
        # Song info
        song_info_label = ctk.CTkLabel(
            self.context_menu,
            text=song_data.get('title', 'Unknown Song')[:30] + "..." if len(song_data.get('title', '')) > 30 else song_data.get('title', 'Unknown Song'),
            font=ctk.CTkFont(size=12),
            text_color="#888888"
        )
        song_info_label.pack(pady=(0, 15))
        
        # Get user playlists
        playlists = self.firebase_manager.get_user_playlists(self.current_user)
        
        if not playlists:
            # Show message if no playlists
            no_playlist_label = ctk.CTkLabel(
                self.context_menu,
                text="No playlists found.\nCreate a playlist first.",
                font=ctk.CTkFont(size=12),
                text_color="#888888"
            )
            no_playlist_label.pack(pady=15)
        else:
            # Create scrollable frame for playlists
            canvas = ctk.CTkCanvas(self.context_menu, bg="#2a2a2a", highlightthickness=0, height=120)
            scrollbar = ctk.CTkScrollbar(self.context_menu, orientation="vertical", command=canvas.yview)
            scrollable_frame = ctk.CTkFrame(canvas, fg_color="transparent")
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            canvas.pack(side="left", fill="both", expand=True, padx=10, pady=5)
            scrollbar.pack(side="right", fill="y", padx=(0, 10), pady=5)
            
            # Add playlist options
            for i, playlist in enumerate(playlists):
                playlist_btn = ctk.CTkButton(
                    scrollable_frame,
                    text=playlist["name"],
                    font=ctk.CTkFont(size=12),
                    fg_color="#333333",
                    hover_color="#444444",
                    anchor="w",
                    command=lambda p=playlist, s=song_data: self._add_to_playlist(p, s),
                    height=30
                )
                playlist_btn.pack(fill="x", padx=5, pady=1)
            
            # Update canvas scroll region
            canvas.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))
        
        # Cancel button
        cancel_btn = ctk.CTkButton(
            self.context_menu,
            text="Cancel",
            font=ctk.CTkFont(size=12),
            fg_color="#666666",
            hover_color="#777777",
            command=self._hide_context_menu,
            height=30
        )
        cancel_btn.pack(pady=(10, 15))
        
        # Bind click outside to close menu - bind to the main window
        self.winfo_toplevel().bind("<Button-1>", self._on_window_click_context_menu)

    def _hide_context_menu(self):
        """Hide the context menu"""
        if hasattr(self, 'context_menu'):
            self.context_menu.place_forget()
            self.context_menu = None
            # Unbind the click handler
            self.winfo_toplevel().unbind("<Button-1>")

    def _on_window_click_context_menu(self, event):
        """Handle clicks outside the context menu to close it"""
        if hasattr(self, 'context_menu') and self.context_menu:
            # Get the widget that was clicked
            clicked_widget = event.widget
            
            # Check if the click was outside the context menu
            if clicked_widget != self.context_menu and not self.context_menu.winfo_containing(event.x_root, event.y_root):
                self._hide_context_menu()

    def _add_to_playlist(self, playlist, song_data):
        """Add song to selected playlist"""
        if self.add_to_playlist_callback:
            self.add_to_playlist_callback(song_data, playlist)
        
        # Show success message
        success_label = ctk.CTkLabel(
            self.context_menu,
            text=f"✓ Added to '{playlist['name']}'",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#1DB954"
        )
        success_label.pack(pady=5)
        
        # Hide menu after a short delay
        self.after(1500, self._hide_context_menu)
    
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
        
        # Like button (only show if user is logged in)
        like_button = None
        if self.current_user and self.firebase_manager:
            # Check if song is already liked
            is_liked = self.firebase_manager.is_song_liked(self.current_user, result.get('videoId'))
            
            # Use consistent heart symbols with appropriate font sizes
            if is_liked:
                like_text = "♥"
                like_font = ctk.CTkFont(size=14)  # Smaller font for filled heart
                like_color = "#FF6B6B"
                like_hover = "#FF5252"
            else:
                like_text = "♡"
                like_font = ctk.CTkFont(size=16)  # Normal font for empty heart
                like_color = "#333333"
                like_hover = "#444444"
            
            like_button = ctk.CTkButton(
                card,
                text=like_text,
                width=40,
                height=40,
                corner_radius=20,
                fg_color=like_color,
                hover_color=like_hover,
                text_color="#FFFFFF",
                font=like_font,
                command=lambda r=result: self._on_like_button_clicked(r, like_button)
            )
            like_button.grid(row=0, column=2, rowspan=2, padx=(0, 10), pady=15, sticky="nsew")
        
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
            command=lambda: self._on_song_selected(result)
        )
        play_btn.grid(row=0, column=3, rowspan=2, padx=(0, 15), pady=15, sticky="nsew")
        
        # Hover + right-click across entire card area
        hover_on_color = "#333333"
        hover_off_color = "#222222"

        def set_hover(is_on: bool):
            color = hover_on_color if is_on else hover_off_color
            card.configure(fg_color=color)
            # paint inner frames too so the whole card looks hovered
            content_frame.configure(fg_color=color if is_on else "transparent")
            thumb_container.configure(fg_color=color if is_on else "transparent")

        def on_enter(_):
            set_hover(True)

        def on_leave(e):
            w = self.winfo_containing(e.x_root, e.y_root)
            if not w or not self._is_descendant_of(w, card):
                set_hover(False)

        def bind_recursive(widget):
            widget.bind("<Enter>", on_enter)
            widget.bind("<Leave>", on_leave)
            widget.bind("<Button-3>", lambda ev: self._on_right_click(ev, result))
            for child in widget.winfo_children():
                bind_recursive(child)

        if self.current_user:
            bind_recursive(card)

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
            # Calculate available width for the title (total width - thumbnail - buttons - paddings)
            available_width = max(100, card.winfo_width() - 270)  # 270 = thumbnail(120) + like button(40) + play button(60) + paddings(50)
            title.configure(wraplength=available_width)
            
        # Bind to card resize
        card.bind('<Configure>', update_wraplength)
        
    def get_all_video_ids(self):
        # Return all video IDs currently shown
        if hasattr(self, '_video_ids'):
            return list(self._video_ids)
        return []

    def _is_descendant_of(self, widget, parent):
        while widget is not None:
            if widget == parent:
                return True
            widget = widget.master
        return False