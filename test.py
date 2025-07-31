import customtkinter as ctk
from PIL import Image, ImageTk
import os
import yt_dlp
from searchscreen import SearchScreen
import threading
import time
import concurrent.futures
import json
from functools import lru_cache
import math
from LoginClass import LoginWindow

# Setup
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue") 

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        window_width = 1920
        window_height = 1080
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.title("HanyaMusic")
        
        # Configure window resizing
        self.minsize(800, 600)  # Set minimum window size
        self.grid_rowconfigure(0, weight=1)  # Main content area
        self.grid_rowconfigure(1, weight=0)  # Music player area (fixed height)
        self.grid_columnconfigure(0, weight=1)
        
        # Disable window resizing animation on Windows
        try:
            self.wm_attributes('-zoomed', False)  # Disable zoomed state
            self.update_idletasks()
            self.wm_attributes('-fullscreen', False)
        except Exception:
            pass
            
        # Prevent window from being resized too small
        self.update_idletasks()
        
        # State
        self.menu_visible = False
        self.search_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)  # Increased workers
        self.current_search_future = None
        self.current_search_query = ""
        self.search_delay = 200  # Reduced delay for better responsiveness
        self.after_id = None
        self._resize_in_progress = False
        self._resize_after_id = None

        # Pre-compiled regex patterns and cache
        self.duration_cache = {}
        self.view_cache = {}

        # Music player state
        self.music_player = None
        self.current_playlist = []
        self.current_song_index = 0

        # Configure yt-dlp options - optimized for speed
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'default_search': 'ytsearch50:',  # Reduced from 100 to 50 for faster response
            'no_check_certificate': True,
            'ignoreerrors': True,
            'geo_bypass': True,
            'noplaylist': True,
            'skip_download': True,
            'socket_timeout': 10,  # Add timeout
            'retries': 1,  # Reduce retries
        }

        # User state
        self.current_user = None
        self.logged_in = False

        # Layout containers
        self.create_main_area()
        self.create_topbar()
        self.create_music_player_area()
        
        # Bind window events
        self.bind('<Configure>', self._on_window_configure)

    def create_music_player_area(self):
        """Create the area at the bottom for the music player"""
        # Create a frame at the bottom for the music player - initially hidden
        self.music_player_frame = ctk.CTkFrame(self, fg_color="transparent", height=240)
        self.music_player_frame.grid(row=1, column=0, sticky="ew", padx=0, pady=0)
        self.music_player_frame.grid_propagate(False)  # Prevent resizing
        self.music_player_frame.grid_columnconfigure(0, weight=1)
        
        # Initially hide the music player frame
        self.music_player_frame.grid_remove()

    def create_topbar(self):
        search_font = ctk.CTkFont(family="Helvetica", size=18)

        # Frame to hold search bar and icon together
        self.search_frame = ctk.CTkFrame(self, width=600, height=40, corner_radius=10, fg_color="#1a1a1a")
        self.search_frame.place(relx=0.5, y=10, anchor="n")

        # Load magnifying glass icon
        search_icon = self.load_search_icon()

        # Icon Label (left icon)
        self.search_icon_label = ctk.CTkLabel(self.search_frame, text="", image=search_icon, width=30)
        self.search_icon_label.place(x=10, rely=0.5, anchor="w")

        # Entry
        self.searchbar = ctk.CTkEntry(
            self.search_frame,
            placeholder_text="Search...",
            width=550,
            height=36,
            font=search_font,
            corner_radius=10
        )
        self.searchbar.place(x=48, y=2)
        
        # Bind focus in/out events
        self.searchbar.bind('<FocusIn>', self.on_search_focus_in)
        self.searchbar.bind('<FocusOut>', self.on_search_focus_out)
        
        # Initially disable search typing handler
        self.search_enabled = False
        
        self.loading_label = None

        # User section frame to hold username and icon
        self.user_section = ctk.CTkFrame(self, fg_color="transparent")
        self.user_section.place(relx=0.95, y=10, anchor="ne")
        
        # Username label (initially hidden)
        self.username_label = ctk.CTkLabel(
            self.user_section,
            text="",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#1DB954"
        )
        # Don't pack initially - will be shown when logged in
        
        # User icon with dropdown menu
        self.user_icon = ctk.CTkButton(
            self.user_section, 
            text="", 
            image=self.load_user_icon(), 
            width=40, 
            height=40,
            fg_color="transparent",
            hover_color="#333333",
            command=self.toggle_user_menu
        )
        self.user_icon.pack(side="right")
        
        # Create user menu (initially hidden)
        self.user_menu = ctk.CTkFrame(
            self,
            width=150,
            corner_radius=5,
            fg_color="#282828",
            border_width=1,
            border_color="#444444"
        )
        self.user_menu_visible = False
        
        # Menu items (will be updated based on login status)
        self.menu_items = [
            ("Log In", self.on_login_clicked),
            ("Settings", self.on_settings_clicked),
            ("About", self.on_about_clicked)
        ]
        
        self.create_user_menu()
        
        # 'X' Button to clear input
        self.clear_button = ctk.CTkButton(
            self.search_frame,
            text="✕",
            width=24,
            height=24,
            font=ctk.CTkFont(size=16),
            fg_color="transparent",
            command=self.clear_searchbar
        )
        self.clear_button.place(x=570, rely=0.5, anchor="center")
        
        # Bind click outside to close menu
        self.bind("<Button-1>", self.on_window_click)

    def toggle_user_menu(self):
        """Toggle the visibility of the user menu"""
        if self.user_menu_visible:
            self.hide_user_menu()
        else:
            self.show_user_menu()
    
    def show_user_menu(self):
        """Show the user menu below the user icon"""
        if not self.user_menu_visible:
            self.update_user_menu_position()
            self.user_menu_visible = True
    
    def hide_user_menu(self):
        """Hide the user menu"""
        if self.user_menu_visible:
            self.user_menu.place_forget()
            self.user_menu_visible = False
    
    def on_window_click(self, event):
        """Handle clicks outside the user menu to close it"""
        if self.user_menu_visible:
            # Check if click was outside both user icon and menu
            if not (self.user_icon.winfo_containing(event.x_root, event.y_root) or 
                   self.user_menu.winfo_containing(event.x_root, event.y_root)):
                self.hide_user_menu()
    
    def on_login_clicked(self):
        """Handle login menu item click"""
        self.hide_user_menu()
        # Create and show login window
        login_window = LoginWindow(self, on_login_success=self.on_login_success)
        # Set focus to the login window
        login_window.focus_force()
    
    def on_login_success(self, username):
        """Handle successful login"""
        self.current_user = username
        self.logged_in = True
        print(f"Successfully logged in as {username}")
        
        # Show username to the left of user icon
        self.username_label.configure(text=username)
        self.username_label.pack(side="left", padx=(0, 10))
        
        # Update menu items to show Log Out instead of Log In
        self.menu_items = [
            ("Log Out", self.on_logout_clicked),
            ("Settings", self.on_settings_clicked),
            ("About", self.on_about_clicked)
        ]
        
        # Recreate the menu with updated items
        self.create_user_menu()
        
        # Update user icon to show logged in state
        try:
            # You could load a different icon for logged-in users
            logged_in_icon = self.load_user_icon()  # Or load a different icon
            self.user_icon.configure(image=logged_in_icon)
        except Exception as e:
            print(f"Error updating user icon: {e}")

    def on_logout_clicked(self):
        """Handle logout menu item click"""
        self.hide_user_menu()
        
        # Clear user state
        self.current_user = None
        self.logged_in = False
        
        # Hide username
        self.username_label.configure(text="")
        self.username_label.pack_forget()
        
        # Update menu items back to Log In
        self.menu_items = [
            ("Log In", self.on_login_clicked),
            ("Settings", self.on_settings_clicked),
            ("About", self.on_about_clicked)
        ]
        
        # Recreate the menu with updated items
        self.create_user_menu()
        
        print("User logged out")

    def on_settings_clicked(self):
        """Handle settings menu item click"""
        print("Settings clicked")
        self.hide_user_menu()
        # Add your settings logic here
    
    def on_about_clicked(self):
        """Handle about menu item click"""
        print("About clicked")
        self.hide_user_menu()
        # Add your about dialog here

    def create_main_area(self):
        self.main_frame = ctk.CTkFrame(self, fg_color="black")
        self.main_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=(60, 0))

    def show_main_frame(self):
        # Clear main_frame and recreate it
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        self.main_frame = ctk.CTkFrame(self, fg_color="black")
        self.main_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=(60, 0))

    def clear_searchbar(self):
        self.searchbar.delete(0, 'end')
        # Cancel any pending searches
        if self.after_id:
            self.after_cancel(self.after_id)
        if self.current_search_future and not self.current_search_future.done():
            self.current_search_future.cancel()
        self.show_main_frame()

    @lru_cache(maxsize=1)
    def load_search_icon(self):
        try:
            icon_path = os.path.join("public", "icon", "search.png")
            image = Image.open(icon_path)
            image = image.resize((24, 24), Image.LANCZOS)
            return ctk.CTkImage(light_image=image, dark_image=image, size=(24, 24))
        except Exception as e:
            print(f"Could not load search icon: {e}")
            return None

    @lru_cache(maxsize=1)
    def load_user_icon(self):
        try:
            icon_path = os.path.join("public", "icon", "profile.png")
            image = Image.open(icon_path)
            image = image.resize((40, 40), Image.LANCZOS)
            return ctk.CTkImage(light_image=image, dark_image=image, size=(40, 40))
        except Exception as e:
            print(f"Could not load user icon: {e}")
            return None

    def on_search_focus_in(self, event):
        """Called when search bar gets focus"""
        self.search_enabled = True
        # Re-bind the key release event when search bar is focused
        self.searchbar.bind('<KeyRelease>', self.on_search_typing)
        
    def on_search_focus_out(self, event):
        """Called when search bar loses focus"""
        self.search_enabled = False
        # Unbind the key release event when search bar loses focus
        self.searchbar.unbind('<KeyRelease>')

    def on_search_typing(self, event=None):
        """Handle search typing - only called when search bar is focused"""
        if not self.search_enabled:
            return
            
        # Cancel any pending search
        if self.after_id:
            self.after_cancel(self.after_id)
        
        # Cancel current search if running
        if self.current_search_future and not self.current_search_future.done():
            self.current_search_future.cancel()
        
        # Get current query
        query = self.searchbar.get().strip()
        self.current_search_query = query
        
        # If search field is empty, show main frame
        if not query:
            self.show_main_frame()
            return
        
        # Minimum query length to reduce unnecessary API calls
        if len(query) < 2:
            return
            
        # Show loading state
        self.show_loading()
        
        # Schedule search with delay
        self.after_id = self.after(self.search_delay, self.initiate_search)

    def initiate_search(self):
        query = self.current_search_query
        if not query:
            return
        
        # Cancel previous search if still running
        if self.current_search_future and not self.current_search_future.done():
            self.current_search_future.cancel()
        
        # Submit new search
        self.current_search_future = self.search_executor.submit(self.perform_search, query)
        
        # Monitor the search with timeout
        self.monitor_search(query, self.current_search_future)

    def monitor_search(self, query, future, timeout=10):  # Reduced timeout
        """Monitor search progress with timeout"""
        def check_result():
            try:
                if future.cancelled():
                    return
                
                if future.done():
                    try:
                        results = future.result(timeout=0.1)
                        if query == self.current_search_query:  # Still relevant
                            # Process results in background thread for better UI responsiveness
                            self.after_idle(lambda: self.display_results(results))
                    except Exception as e:
                        print(f"Search error: {e}")
                        if query == self.current_search_query:
                            self.display_error("Search failed. Please try again.")
                else:
                    # Check if we've exceeded timeout
                    elapsed = time.time() - start_time
                    if elapsed > timeout:
                        future.cancel()
                        if query == self.current_search_query:
                            self.display_error("Search timed out. Please try again.")
                    else:
                        # Check again in 50ms for better responsiveness
                        self.after(50, check_result)
            except Exception as e:
                print(f"Monitor error: {e}")
                if query == self.current_search_query:
                    self.display_error("An error occurred. Please try again.")
        
        start_time = time.time()
        check_result()

    def perform_search(self, query, offset=0, exclude_ids=None, batch_size=10):
        """Perform the actual search using yt-dlp - now supports pagination and exclusion."""
        if not query:
            return []
        if exclude_ids is None:
            exclude_ids = set()
        else:
            exclude_ids = set(exclude_ids)
        try:
            print(f"Searching for: {query} (offset={offset}, exclude={len(exclude_ids)})")
            # Streamlined yt-dlp options for speed
            search_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'skip_download': True,
                'ignoreerrors': True,
                'socket_timeout': 8,
                'retries': 1,
                'format': 'best',
            }
            # Fetch more results than needed to allow for exclusion
            fetch_count = max(batch_size * 2, 30)
            with yt_dlp.YoutubeDL(search_opts) as ydl:
                search_results = ydl.extract_info(
                    f"ytsearch{fetch_count + offset}:{query}",
                    download=False
                )
            print(f"yt-dlp response received")
            if not search_results or 'entries' not in search_results:
                print("No entries in search results")
                return []
            entries = search_results.get('entries', [])
            # Skip offset and filter out excluded IDs
            filtered = []
            seen = set()
            for entry in entries[offset:]:
                if not entry or not entry.get('id'):
                    continue
                vid = entry['id']
                if vid in exclude_ids or vid in seen:
                    continue
                seen.add(vid)
                title = entry.get('title', 'No Title')
                uploader = entry.get('uploader', 'Unknown')
                duration = entry.get('duration')
                view_count = entry.get('view_count')
                
                # Skip if title and uploader are the same (after case-insensitive comparison)
                if str(title).strip().lower() == str(uploader).strip().lower():
                    continue
                    
                # Skip if duration is 0 or invalid
                if not duration or duration <= 0:
                    continue
                    
                result = {
                    'title': str(title).strip()[:100],
                    'thumbnail_url': f"https://img.youtube.com/vi/{vid}/mqdefault.jpg",
                    'videoId': vid,
                    'uploader': str(uploader).strip()[:50] if uploader else 'Unknown',
                    'duration': self.format_duration_fast(duration),
                    'view_count': self.format_views_fast(view_count),
                    'url': f"https://www.youtube.com/watch?v={vid}"
                }
                filtered.append(result)
                if len(filtered) >= batch_size:
                    break
            print(f"Processed {len(filtered)} results (offset={offset})")
            return filtered
        except Exception as e:
            print(f"yt-dlp search failed: {str(e)}")
            return []

    def load_more_results(self, callback, batch_size=10):
        """Called by SearchScreen to load more results for infinite scroll."""
        query = self.current_search_query
        if not query:
            callback([])
            return
        # Gather all video IDs currently shown
        if hasattr(self, 'search_screen') and hasattr(self.search_screen, 'get_all_video_ids'):
            exclude_ids = self.search_screen.get_all_video_ids()
        else:
            exclude_ids = []
        offset = len(exclude_ids)
        def do_search():
            results = self.perform_search(query, offset=offset, exclude_ids=exclude_ids, batch_size=batch_size)
            self.after_idle(lambda: callback(results))
        threading.Thread(target=do_search, daemon=True).start()

    def format_duration_fast(self, seconds):
        """Optimized duration formatting with caching"""
        if not seconds or seconds <= 0:
            return "0:00"
        
        # Use cache for common durations
        if seconds in self.duration_cache:
            return self.duration_cache[seconds]
        
        # Quick integer operations
        minutes, secs = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        
        if hours > 0:
            result = f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            result = f"{minutes}:{secs:02d}"
        
        # Cache result
        self.duration_cache[seconds] = result
        return result

    def format_views_fast(self, view_count):
        """Optimized view formatting with caching"""
        if not view_count or view_count <= 0:
            return "0 views"
        
        # Use cache for common view counts
        if view_count in self.view_cache:
            return self.view_cache[view_count]
        
        # Quick formatting
        if view_count >= 1_000_000:
            result = f"{view_count // 100000 / 10:.1f}M views"
        elif view_count >= 1_000:
            result = f"{view_count // 100 / 10:.1f}K views"
        else:
            result = f"{view_count} views"
        
        # Cache result
        self.view_cache[view_count] = result
        return result

    def show_loading(self):
        """Show animated loading state with a modern spinner"""
        # Clear existing widgets
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        
        # Create container for centered content
        container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        container.pack(expand=True, fill="both")
        
        # Add loading text with dot animation
        self.loading_text = ctk.CTkLabel(
            container,
            text="Searching",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#1DB954"
        )
        self.loading_text.pack(pady=(0, 20))
        
        # Create a frame for the spinner
        spinner_frame = ctk.CTkFrame(container, fg_color="transparent", width=80, height=80)
        spinner_frame.pack(pady=10)
        spinner_frame.pack_propagate(False)
        
        # Create spinner canvas
        self.spinner_canvas = ctk.CTkCanvas(
            spinner_frame,
            width=60,
            height=60,
            bg="#000000",
            highlightthickness=0
        )
        self.spinner_canvas.pack(expand=True)
        
        # Animation variables
        self.spinner_angle = 0
        self.dot_radius = 5
        self.spinner_colors = [
            "#1DB954", "#1ed760", "#4dff9d", 
            "#4dff9d", "#1ed760", "#1DB954"
        ]
        
        # Start the animation
        self.animate_spinner()

    def animate_spinner(self):
        """Animate the loading spinner"""
        if not hasattr(self, 'spinner_canvas') or not self.spinner_canvas.winfo_exists():
            return
            
        canvas = self.spinner_canvas
        canvas.delete("all")
        
        center_x = canvas.winfo_width() // 2
        center_y = canvas.winfo_height() // 2
        radius = 20
        
        # Draw the spinner dots
        for i in range(6):
            angle = self.spinner_angle + (i * 60)
            rad = math.radians(angle)
            x = center_x + (radius * math.cos(rad))
            y = center_y + (radius * math.sin(rad))
            
            # Calculate alpha for fading effect (0.3 to 1.0)
            alpha = 0.3 + (0.7 * (i / 5.0))
            color = self.add_alpha_to_hex(self.spinner_colors[i], alpha)
            
            canvas.create_oval(
                x - self.dot_radius, y - self.dot_radius,
                x + self.dot_radius, y + self.dot_radius,
                fill=color, outline=""
            )
        
        # Update the angle for next frame
        self.spinner_angle = (self.spinner_angle + 6) % 360
        
        # Update the searching dots
        dots = "." * ((self.spinner_angle // 60) % 4)
        if hasattr(self, 'loading_text') and self.loading_text.winfo_exists():
            self.loading_text.configure(text=f"Searching{dots}")
        
        # Schedule next frame
        self.after(100, self.animate_spinner)

    def add_alpha_to_hex(self, hex_color, alpha):
        """Add alpha value to a hex color"""
        if alpha < 0:
            alpha = 0
        elif alpha > 1:
            alpha = 1
            
        # Convert hex to RGB
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        
        # Create a darker version for the spinner
        r = max(0, int(r * 0.7))
        g = max(0, int(g * 0.7))
        b = max(0, int(b * 0.7))
        
        return f'#{r:02x}{g:02x}{b:02x}'

    def display_error(self, error_message):
        """Display error message"""
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        
        error_label = ctk.CTkLabel(
            self.main_frame, 
            text=error_message, 
            font=ctk.CTkFont(size=18),
            text_color="red"
        )
        error_label.pack(pady=40)

    def display_results(self, results):
        """Display search results"""
        # Clear previous results
        for widget in self.main_frame.winfo_children():
            widget.destroy()
            
        # Create search results screen
        self.search_screen = SearchScreen(self.main_frame, results, self.load_more_results)  # Store as instance variable
        self.search_screen.pack(fill="both", expand=True)
        
        # Set song selection callback
        self.search_screen.set_song_selection_callback(self.on_song_selected)
        
        # Remove focus from search bar and stop listening to keyboard
        self.focus_set()  # Move focus to main window
        self.searchbar.unbind('<KeyRelease>')
        self.search_enabled = False
        
        # Finalize display after a short delay to ensure everything is rendered
        self.after(100, lambda: self.finalize_display(self.search_screen))
    
    def on_song_selected(self, song_data, playlist, current_index):
        """Called when a song is selected from the search results"""
        # Update the current playlist and song index
        self.current_playlist = playlist
        self.current_song_index = current_index
        
        # Show the music player frame
        self.music_player_frame.grid()
        
        # Create or update the music player
        if self.music_player:
            # Update existing player with new song
            self.music_player.set_playlist(playlist, current_index)
        else:
            # Create new music player
            from playerClass import MusicPlayerContainer
            self.music_player = MusicPlayerContainer(self.music_player_frame, song_data, playlist, current_index)
            self.music_player.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
            
            # Set callback for song changes
            self.music_player.set_on_song_change_callback(self.on_song_change)
            # Set callback for when player is closed
            self.music_player.set_on_close_callback(self.hide_music_player)
        
        # Update the layout to accommodate the music player
        self.update_idletasks()
        
        print(f"Now playing: {song_data.get('title', 'Unknown Title')} (index: {current_index})")
    
    def on_song_change(self, index, song_data):
        """Callback when song changes in the player"""
        self.current_song_index = index
        print(f"Now playing: {song_data.get('title', 'Unknown Title')} (index: {index})")
        # You can add additional logic here, like updating the UI to highlight the current song
    
    def hide_music_player(self):
        """Hide the music player frame"""
        if self.music_player:
            self.music_player.destroy()
            self.music_player = None
        self.music_player_frame.grid_remove()
        # Update the layout after hiding the music player
        self.update_idletasks()
        print("Music player hidden")

    def finalize_display(self, search_screen):
        """Finalize display setup after UI is rendered"""
        try:
            # Update scroll region
            search_screen.canvas.configure(scrollregion=search_screen.canvas.bbox("all"))
            search_screen.canvas.update_idletasks()
            
            # Force a single update to ensure everything is drawn
            self.update_idletasks()
            
        except Exception as e:
            print(f"Error finalizing display: {e}")

    def _on_window_configure(self, event):
        """Handle window resize events with debounce"""
        if not self._resize_in_progress:
            self._resize_in_progress = True
            if self._resize_after_id:
                self.after_cancel(self._resize_after_id)
            self._resize_after_id = self.after(100, self._process_resize)
    
    def _process_resize(self):
        """Process window resize - update menu position if visible"""
        self._resize_in_progress = False
        if self.user_menu_visible:
            self.update_user_menu_position()
    
    def update_user_menu_position(self):
        """Update the position of the user menu to follow the user icon"""
        if hasattr(self, 'user_icon') and hasattr(self, 'user_menu'):
            # Get position of user section relative to the window
            section_x = self.user_section.winfo_x()
            section_y = self.user_section.winfo_y()
            section_width = self.user_section.winfo_width()
            
            # Calculate position to align menu with right edge of user section
            menu_width = self.user_menu.winfo_reqwidth()
            menu_x = section_x + section_width - menu_width
            
            # Position the menu below the user section
            menu_y = section_y + self.user_section.winfo_height() + 5
            
            # Position the menu
            self.user_menu.place(x=menu_x, y=menu_y)
            self.user_menu.lift()

    def create_user_menu(self):
        """Recreate the user menu with updated items"""
        for widget in self.user_menu.winfo_children():
            widget.destroy()
        
        for i, (text, command) in enumerate(self.menu_items):
            btn = ctk.CTkButton(
                self.user_menu,
                text=text,
                font=ctk.CTkFont(size=14),
                fg_color="transparent",
                hover_color="#404040",
                anchor="w",
                command=command,
                height=40
            )
            btn.pack(fill="x", padx=5, pady=2 if i < len(self.menu_items) - 1 else 5)
            
            # Add separator between items
            if i < len(self.menu_items) - 1:
                ctk.CTkFrame(self.user_menu, height=1, fg_color="#444444").pack(fill="x", padx=5)

    def __del__(self):
        """Cleanup when app is destroyed"""
        if hasattr(self, 'search_executor'):
            self.search_executor.shutdown(wait=False)

if __name__ == "__main__":
    app = App()
    app.mainloop()