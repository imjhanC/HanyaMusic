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
        self.grid_rowconfigure(0, weight=1)
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

        # Layout containers
        self.create_main_area()
        self.create_topbar()
        
        # Bind window events
        self.bind('<Configure>', self._on_window_configure)

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
        self.searchbar.bind('<KeyRelease>', self.on_search_typing)  
        self.loading_label = None

        self.user_icon = ctk.CTkLabel(self, text="", image=self.load_user_icon(), width=40, height=40)
        self.user_icon.place(relx=0.95, y=10, anchor="ne")

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

    def create_main_area(self):
        self.main_frame = ctk.CTkFrame(self, fg_color="black")
        self.main_frame.place(x=0, y=60, relwidth=1, relheight=1, anchor="nw")

    def show_main_frame(self):
        # Clear main_frame and recreate it
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        self.main_frame = ctk.CTkFrame(self, fg_color="black")
        self.main_frame.place(x=0, y=60, relwidth=1, relheight=1, anchor="nw")

    def on_search_typing(self, event=None):
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
            
        # Show loading immediately
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
        """Show loading state"""
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        
        self.loading_label = ctk.CTkLabel(
            self.main_frame, 
            text="Searching...", 
            font=ctk.CTkFont(size=24)
        )
        self.loading_label.pack(pady=40)

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
        """Optimized results display with progressive loading and infinite scroll support."""
        # Clear the main frame
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        if not results:
            self.display_error("No results found. Try a different search term.")
            return
        try:
            container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
            container.pack(fill="both", expand=True)
            container.grid_rowconfigure(0, weight=1)
            container.grid_columnconfigure(0, weight=1)
            # Pass a load_more callback to SearchScreen
            def load_more_callback(cb):
                self.load_more_results(cb, batch_size=10)
            self.search_screen = SearchScreen(container, results, load_more_callback=load_more_callback)
            self.search_screen.grid(row=0, column=0, sticky="nsew")
            self.after_idle(lambda: self.finalize_display(self.search_screen))
        except Exception as e:
            print(f"Error displaying results: {e}")
            self.display_error("Error displaying results. Please try again.")
    
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
        """Handle window resize with debounce"""
        if event.widget != self:  # Only process main window resize
            return
            
        if self._resize_after_id:
            self.after_cancel(self._resize_after_id)
            
        self._resize_after_id = self.after(200, self._process_resize)
    
    def _process_resize(self):
        """Process resize after a short delay to prevent excessive updates"""
        if self._resize_in_progress:
            return
            
        self._resize_in_progress = True
        try:
            # Update any layout that needs to respond to window size
            if hasattr(self, 'search_frame'):
                # Update search bar width
                window_width = self.winfo_width()
                search_width = min(600, max(300, window_width - 200))  # Keep search bar between 300-600px
                self.search_frame.configure(width=search_width)
                
                # Update search bar position
                if hasattr(self, 'search_bar'):
                    self.search_bar.configure(width=search_width - 40)  # Account for padding
        finally:
            self._resize_after_id = None
            self._resize_in_progress = False

    def __del__(self):
        """Cleanup when app is destroyed"""
        if hasattr(self, 'search_executor'):
            self.search_executor.shutdown(wait=False)

if __name__ == "__main__":
    app = App()
    app.mainloop()