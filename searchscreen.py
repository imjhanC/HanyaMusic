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
        
        # Selection state and colors
        self._selected_card = None
        self._card_color_default = "#222222"
        self._card_color_hover = "#333333"
        self._card_color_selected = "#444444"
        
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

        self._menu_open = False
        self._scroll_disabled = False
        self._saved_scroll_cmd = None
        self.context_menu = None
        self.submenu = None
    
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
        # Select the card that was right-clicked
        try:
            card = self._get_card_from_event(event)
            if card is not None:
                self._select_card(card)
        except Exception:
            pass
        if not self.current_user or not self.add_to_playlist_callback:
            return
        
        # Create context menu
        self._show_context_menu(event, song_data)
    
    def _show_context_menu(self, event, song_data):
        # Close previous menus
        self._hide_all_menus()

        # Build primary menu
        self.context_menu = ctk.CTkFrame(
            self,
            width=230,
            corner_radius=8,
            fg_color="#2a2a2a",
            border_width=1,
            border_color="#444444"
        )

        # Position bottom-right of cursor; fallback upper-right if blocked
        window_w, window_h = self.winfo_width(), self.winfo_height()
        menu_w, menu_h = 230, 120
        # convert to coordinates relative to self
        cursor_x = event.x_root - self.winfo_rootx()
        cursor_y = event.y_root - self.winfo_rooty()

        x = cursor_x + 5
        y = cursor_y + 5
        if x + menu_w > window_w:
            x = cursor_x - menu_w - 5
        if y + menu_h > window_h:
            y = cursor_y - menu_h - 5
        x = max(5, min(x, window_w - menu_w - 5))
        y = max(5, min(y, window_h - menu_h - 5))

        self.context_menu.place(x=x, y=y)
        self.context_menu.lift()

        # Row: "Add to playlist >"
        add_row = ctk.CTkFrame(self.context_menu, fg_color="transparent")
        add_row.pack(fill="x", padx=10, pady=(10, 5))

        left = ctk.CTkLabel(add_row, text="Add to playlist", font=ctk.CTkFont(size=14), text_color="#FFFFFF")
        right = ctk.CTkLabel(add_row, text="❯", font=ctk.CTkFont(size=14, weight="bold"), text_color="#BBBBBB")
        left.pack(side="left")
        right.pack(side="right")

        def _row_enter(_):
            add_row.configure(fg_color="#3a3a3a")
            self._ensure_playlist_submenu(add_row, song_data)

        def _row_leave(_):
            add_row.configure(fg_color="transparent")
            # Only schedule hide if we're not moving to the submenu
            self._schedule_hide_submenu_if_not_in_submenu()

        for w in (add_row, left, right):
            w.bind("<Enter>", _row_enter)
            w.bind("<Leave>", _row_leave)

        # Separator
        ctk.CTkFrame(self.context_menu, height=1, fg_color="#444444").pack(fill="x", padx=10, pady=5)

        # Cancel
        cancel_btn = ctk.CTkButton(
            self.context_menu,
            text="Cancel",
            font=ctk.CTkFont(size=14),
            fg_color="#666666",
            hover_color="#777777",
            command=self._hide_all_menus,
            height=30
        )
        cancel_btn.pack(fill="x", padx=10, pady=(0, 10))

        # Prevent scroll while menu is open
        self._menu_open = True
        self._disable_scrolling()

        # Close on outside click - bind to all possible parent widgets
        self._bind_outside_click_handlers()

    def _bind_outside_click_handlers(self):
        """Bind click handlers to detect clicks outside menus"""
        # Get the toplevel window
        toplevel = self.winfo_toplevel()
        
        # Bind to various widgets to catch all click events
        widgets_to_bind = [
            toplevel,
            self,
            self.main_container,
            self.canvas_container,
            self.canvas,
            self.scrollable_frame
        ]
        
        for widget in widgets_to_bind:
            try:
                widget.bind("<Button-1>", self._on_window_click_check_menus, add=True)
                widget.bind("<Button-3>", self._on_window_click_check_menus, add=True)
            except:
                pass

    def _unbind_outside_click_handlers(self):
        """Unbind click handlers when menus are closed"""
        toplevel = self.winfo_toplevel()
        
        widgets_to_unbind = [
            toplevel,
            self,
            self.main_container,
            self.canvas_container,
            self.canvas,
            self.scrollable_frame
        ]
        
        for widget in widgets_to_unbind:
            try:
                widget.unbind("<Button-1>")
                widget.unbind("<Button-3>")
            except:
                pass

    def _hide_all_menus(self):
        """Hide both context menu and submenu"""
        self._hide_playlist_submenu()
        if self.context_menu:
            self.context_menu.place_forget()
            self.context_menu = None
        self._menu_open = False
        self._enable_scrolling()
        self._unbind_outside_click_handlers()

    def _hide_context_menu(self):
        """Legacy method - now calls _hide_all_menus for consistency"""
        self._hide_all_menus()

    def _on_window_click_check_menus(self, event):
        """Check if click is outside both menus and close them if so"""
        if not self.context_menu and not self.submenu:
            return
        
        try:
            # Get the widget that was clicked
            clicked_widget = self.winfo_containing(event.x_root, event.y_root)
            
            # Check if click is inside context menu
            in_context_menu = False
            if self.context_menu:
                in_context_menu = (clicked_widget == self.context_menu or 
                                 self._is_descendant_of(clicked_widget, self.context_menu))
            
            # Check if click is inside submenu
            in_submenu = False
            if self.submenu:
                in_submenu = (clicked_widget == self.submenu or 
                             self._is_descendant_of(clicked_widget, self.submenu))
            
            # If click is outside both menus, close them
            if not in_context_menu and not in_submenu:
                self._hide_all_menus()
                
        except Exception as e:
            # If there's any error in detection, just close menus to be safe
            print(f"Error in click detection: {e}")
            self._hide_all_menus()

    def _add_to_playlist(self, playlist, song_data):
        """Add a song to a playlist using Firebase"""
        if not self.current_user or not self.firebase_manager:
            print("User not logged in or Firebase manager not available")
            return
        
        # Call Firebase method to add song to playlist
        success, message = self.firebase_manager.add_song_to_playlist(
            self.current_user, 
            playlist['name'], 
            song_data
        )
        
        if success:
            # Show success message in context menu
            if self.context_menu:
                ctk.CTkLabel(
                    self.context_menu,
                    text=f"✓ {message}",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color="#1DB954"
                ).pack(pady=5)
            print(message)
        else:
            # Show error message in context menu
            if self.context_menu:
                ctk.CTkLabel(
                    self.context_menu,
                    text=f"✗ {message}",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color="#FF6B6B"
                ).pack(pady=5)
            print(f"Error: {message}")
        
        # Also call the callback if it exists (for backward compatibility)
        if hasattr(self, 'add_to_playlist_callback') and self.add_to_playlist_callback:
            self.add_to_playlist_callback(song_data, playlist)
        
        # Hide menus after a delay
        self.after(900, self._hide_all_menus)
    
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
        if getattr(self, "_menu_open", False):
            return "break"
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self._check_scroll_end(event)

    def _check_scroll_end(self, event=None):
        if getattr(self, "_menu_open", False):
            return
        if self.loading_more or self.no_more_results or not self.load_more_callback:
            return
        try:
            first, last = self.canvas.yview()
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
            fg_color=self._card_color_default,
            corner_radius=10,
            height=100
        )
        
        # Store card reference
        card._title = None  # Will store the title widget reference
        card._content_frame = None
        card._thumb_container = None
        card._is_selected = False
        
        # Configure grid for the card to take full width
        card.grid(row=idx*2, column=0, sticky="nsew", padx=15, pady=5)
        card.grid_columnconfigure(1, weight=1)  # Make the content area expandable
        card.grid_columnconfigure(2, weight=0, minsize=70)  # Make the button column just wide enough
        card.grid_columnconfigure(3, weight=0, minsize=50)  # Make room for like button
        
        # Thumbnail container with fixed aspect ratio
        thumb_container = ctk.CTkFrame(card, fg_color="transparent", width=120, height=80)
        thumb_container.grid(row=0, column=0, rowspan=2, padx=10, pady=10, sticky="nsw")
        thumb_container.grid_propagate(False)  # Prevent container from resizing
        card._thumb_container = thumb_container
        
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
        card._content_frame = content_frame
        
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
            command=lambda c=card, r=result: (self._select_card(c), self._on_song_selected(r))
        )
        play_btn.grid(row=0, column=3, rowspan=2, padx=(0, 15), pady=15, sticky="nsew")
        
        # Hover + right-click across entire card area
        hover_on = self._card_color_hover
        hover_off = self._card_color_default

        def set_hover(is_on: bool):
            # Avoid overriding selection
            if getattr(card, "_is_selected", False):
                return
            color = hover_on if is_on else hover_off
            card.configure(fg_color=color)
            content_frame.configure(fg_color=color if is_on else "transparent")
            thumb_container.configure(fg_color=color if is_on else "transparent")

        def on_enter(_): set_hover(True)

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

        # Allow selecting a card with left-click
        def bind_select_recursive(widget):
            widget.bind("<Button-1>", lambda ev, c=card: self._select_card(c))
            for child in widget.winfo_children():
                bind_select_recursive(child)

        bind_select_recursive(card)

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

    def _get_card_from_event(self, event):
        """Return the enclosing card (from self.cards) for a given event, if any."""
        widget = getattr(event, "widget", None)
        while widget is not None:
            if widget in self.cards:
                return widget
            widget = getattr(widget, "master", None)
        # Fallback via pointer position
        try:
            under_pointer = self.winfo_containing(event.x_root, event.y_root)
            widget = under_pointer
            while widget is not None:
                if widget in self.cards:
                    return widget
                widget = getattr(widget, "master", None)
        except Exception:
            pass
        return None

    def _set_card_selected_visual(self, card, selected):
        """Apply or clear selected visuals for a card and its inner containers."""
        if card is None or not hasattr(card, "winfo_exists") or not card.winfo_exists():
            return
        card._is_selected = bool(selected)
        if selected:
            try:
                card.configure(fg_color=self._card_color_selected)
                if hasattr(card, "_content_frame") and card._content_frame.winfo_exists():
                    card._content_frame.configure(fg_color=self._card_color_selected)
                if hasattr(card, "_thumb_container") and card._thumb_container.winfo_exists():
                    card._thumb_container.configure(fg_color=self._card_color_selected)
            except Exception:
                pass
        else:
            try:
                card.configure(fg_color=self._card_color_default)
                if hasattr(card, "_content_frame") and card._content_frame.winfo_exists():
                    card._content_frame.configure(fg_color="transparent")
                if hasattr(card, "_thumb_container") and card._thumb_container.winfo_exists():
                    card._thumb_container.configure(fg_color="transparent")
            except Exception:
                pass

    def _select_card(self, card):
        """Select the given card and clear any previous selection."""
        if card is self._selected_card:
            self._set_card_selected_visual(card, True)
            return
        if self._selected_card is not None:
            self._set_card_selected_visual(self._selected_card, False)
        self._selected_card = card
        self._set_card_selected_visual(card, True)

    def _cancel_hide_submenu(self):
        if hasattr(self, '_submenu_timer') and self._submenu_timer:
            self.after_cancel(self._submenu_timer)
            self._submenu_timer = None

    def _schedule_hide_submenu(self, delay=200):
        self._cancel_hide_submenu()
        self._submenu_timer = self.after(delay, self._hide_playlist_submenu)

    def _schedule_hide_submenu_if_not_in_submenu(self, delay=100):
        """Schedule hide submenu only if mouse is not in submenu area"""
        def check_and_hide():
            if self.submenu:
                # Get current mouse position
                try:
                    x, y = self.winfo_pointerxy()
                    widget_under_mouse = self.winfo_containing(x, y)
                    
                    # Check if mouse is over submenu or any of its children
                    if widget_under_mouse and self._is_descendant_of(widget_under_mouse, self.submenu):
                        # Mouse is in submenu, don't hide
                        return
                    elif widget_under_mouse == self.submenu:
                        # Mouse is directly on submenu
                        return
                except:
                    pass
                
                # Mouse is not in submenu, hide it
                self._hide_playlist_submenu()
        
        self._cancel_hide_submenu()
        self._submenu_timer = self.after(delay, check_and_hide)

    def _disable_scrolling(self):
        if self._scroll_disabled:
            return
        self._scroll_disabled = True
        try:
            self._saved_scroll_cmd = self.scrollbar.cget("command")
        except Exception:
            self._saved_scroll_cmd = None
        self.scrollbar.configure(command=lambda *args: None)
        self.winfo_toplevel().bind_all("<MouseWheel>", lambda e: "break")

    def _enable_scrolling(self):
        if not self._scroll_disabled:
            return
        self._scroll_disabled = False
        self.scrollbar.configure(command=self.canvas.yview)
        self.winfo_toplevel().unbind_all("<MouseWheel>")
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _ensure_playlist_submenu(self, anchor_widget, song_data):
        self._cancel_hide_submenu()
        if self.submenu:
            self._place_submenu(anchor_widget)
            return
        self._build_playlist_submenu(song_data)
        self._place_submenu(anchor_widget)

    def _build_playlist_submenu(self, song_data):
        self.submenu = ctk.CTkFrame(
            self,
            width=240,
            corner_radius=8,
            fg_color="#2a2a2a",
            border_width=1,
            border_color="#444444"
        )

        ctk.CTkLabel(
            self.submenu,
            text="Choose a playlist",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#FFFFFF"
        ).pack(padx=10, pady=(10, 5), anchor="w")

        container = ctk.CTkFrame(self.submenu, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        canvas = ctk.CTkCanvas(container, bg="#2a2a2a", highlightthickness=0, height=3*36)
        sb = ctk.CTkScrollbar(container, orientation="vertical", command=canvas.yview)
        inner = ctk.CTkFrame(canvas, fg_color="transparent")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        
        # Add mouse wheel scrolling support for the submenu canvas
        def _on_submenu_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        # Bind mouse wheel events to canvas and inner frame
        canvas.bind("<MouseWheel>", _on_submenu_mousewheel)
        inner.bind("<MouseWheel>", _on_submenu_mousewheel)

        playlists = self.firebase_manager.get_user_playlists(self.current_user) or []
        for p in playlists:
            btn = ctk.CTkButton(
                inner,
                text=p["name"],
                font=ctk.CTkFont(size=13),
                fg_color="#333333",
                hover_color="#444444",
                anchor="w",
                height=30,
                command=lambda pl=p: self._add_to_playlist(pl, song_data)
            )
            # Changed from padx=4 to padx=1 to reduce gap to scrollbar
            btn.pack(fill="x", padx=1, pady=2)

        # Fixed hover event handling for the submenu
        def _submenu_enter(event):
            self._cancel_hide_submenu()

        def _submenu_leave(event):
            # Only schedule hide if we're really leaving the submenu area
            self._schedule_hide_submenu_if_not_in_submenu(delay=150)

        # Bind events to the submenu and all its children recursively
        def bind_submenu_events(widget):
            widget.bind("<Enter>", _submenu_enter)
            widget.bind("<Leave>", _submenu_leave)
            # Also bind mouse wheel to playlist buttons for smooth scrolling
            if isinstance(widget, ctk.CTkButton):
                widget.bind("<MouseWheel>", _on_submenu_mousewheel)
            for child in widget.winfo_children():
                bind_submenu_events(child)

        bind_submenu_events(self.submenu)

    def _place_submenu(self, anchor_widget):
        if not self.context_menu or not self.submenu:
            return
        self.submenu.lift()
        ax = anchor_widget.winfo_rootx()
        ay = anchor_widget.winfo_rooty()
        parent_x = self.winfo_rootx()
        parent_y = self.winfo_rooty()
        x = (ax - parent_x) + anchor_widget.winfo_width() + 8
        y = (ay - parent_y)

        window_w, window_h = self.winfo_width(), self.winfo_height()
        submenu_w = 240
        submenu_h = min(3*36 + 50, 260)

        if x + submenu_w > window_w:
            x = (ax - parent_x) - submenu_w - 8
        if y + submenu_h > window_h:
            y = max(5, window_h - submenu_h - 5)

        self.submenu.place(x=x, y=y)

    def _hide_playlist_submenu(self):
        if self.submenu:
            self.submenu.place_forget()
            self.submenu = None