import customtkinter as ctk
from PIL import Image, ImageTk
import os
import yt_dlp
from searchscreen import SearchScreen
import threading
import time
import concurrent.futures
import json

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
        self.resizable(True, True)

        # State
        self.menu_visible = False
        self.search_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.current_search_future = None
        self.current_search_query = ""
        self.search_delay = 300  # Reduced delay for better responsiveness
        self.after_id = None

        # Configure yt-dlp options
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'default_search': 'ytsearch:', # Search YouTube, limit to 20 results
            'no_check_certificate': True,
            'ignoreerrors': True,
            'playlistend': 500,
        }

        # Layout containers
        self.create_main_area()
        self.create_topbar()

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

    def load_search_icon(self):
        try:
            icon_path = os.path.join("public", "icon", "search.png")
            image = Image.open(icon_path)
            image = image.resize((24, 24), Image.LANCZOS)
            return ctk.CTkImage(light_image=image, dark_image=image, size=(24, 24))
        except Exception as e:
            print(f"Could not load search icon: {e}")
            return None

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

    def monitor_search(self, query, future, timeout=15):
        """Monitor search progress with timeout"""
        def check_result():
            try:
                if future.cancelled():
                    return
                
                if future.done():
                    try:
                        results = future.result(timeout=0.1)
                        if query == self.current_search_query:  # Still relevant
                            self.display_results(results)
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
                        # Check again in 100ms
                        self.after(100, check_result)
            except Exception as e:
                print(f"Monitor error: {e}")
                if query == self.current_search_query:
                    self.display_error("An error occurred. Please try again.")
        
        start_time = time.time()
        check_result()

    def perform_search(self, query):
        """Perform the actual search using yt-dlp"""
        if not query:
            return []
        
        try:
            print(f"Searching for: {query}")  # Debug output
            
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                # Search for videos
                search_results = ydl.extract_info(
                    f"ytsearch100:{query}",  # Search for up to 20 results
                    download=False
                )
            
            print(f"yt-dlp response received")  # Debug output
            
            if not search_results or 'entries' not in search_results:
                print("No entries in search results")
                return []
            
            results = []
            entries = search_results.get('entries', [])
            
            for entry in entries:
                if not entry:  # Skip None entries
                    continue
                
                try:
                    video_id = entry.get('id', '')
                    title = entry.get('title', 'No Title')
                    uploader = entry.get('uploader', '')
                    duration = entry.get('duration', 0)
                    view_count = entry.get('view_count', 0)
                    
                    if not video_id:
                        continue
                    
                    # Generate thumbnail URL from video ID
                    thumbnail_url = f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"
                    
                    # Format duration
                    duration_str = self.format_duration(duration) if duration else "Unknown"
                    
                    # Format view count
                    view_str = self.format_views(view_count) if view_count else "Unknown views"
                    
                    results.append({
                        'title': str(title).strip(),
                        'thumbnail_url': thumbnail_url,
                        'videoId': str(video_id).strip(),
                        'uploader': str(uploader).strip() if uploader else 'Unknown',
                        'duration': duration_str,
                        'view_count': view_str,
                        'url': f"https://www.youtube.com/watch?v={video_id}"
                    })
                    
                except Exception as e:
                    print(f"Error processing entry: {e}")
                    continue
            
            print(f"Processed {len(results)} results")  # Debug output
            return results
            
        except Exception as e:
            print(f"yt-dlp search failed: {str(e)}")
            return []

    def format_duration(self, seconds):
        """Format duration in seconds to MM:SS or HH:MM:SS"""
        if not seconds or seconds <= 0:
            return "0:00"
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"

    def format_views(self, view_count):
        """Format view count to readable format"""
        if not view_count or view_count <= 0:
            return "0 views"
        
        if view_count >= 1_000_000:
            return f"{view_count / 1_000_000:.1f}M views"
        elif view_count >= 1_000:
            return f"{view_count / 1_000:.1f}K views"
        else:
            return f"{view_count} views"

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
        """Display search results"""
        # Clear the main frame
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        
        if not results:
            self.display_error("No results found. Try a different search term.")
            return
        
        try:
            # Create a container frame that fills the available space
            container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
            container.pack(fill="both", expand=True)
            
            # Configure grid weights for the container
            container.grid_rowconfigure(0, weight=1)
            container.grid_columnconfigure(0, weight=1)
            
            # Create the search screen inside the container
            search_screen = SearchScreen(container, results)
            search_screen.grid(row=0, column=0, sticky="nsew")
            
            # Update the canvas scroll region after a short delay
            self.after(100, lambda: self.update_scroll_region(search_screen))
            
        except Exception as e:
            print(f"Error displaying results: {e}")
            self.display_error("Error displaying results. Please try again.")
    
    def update_scroll_region(self, search_screen):
        """Update the canvas scroll region after widgets are drawn"""
        try:
            search_screen.canvas.configure(scrollregion=search_screen.canvas.bbox("all"))
            # Update the canvas to ensure it's properly sized
            search_screen.canvas.update_idletasks()
        except Exception as e:
            print(f"Error updating scroll region: {e}")

    def __del__(self):
        """Cleanup when app is destroyed"""
        if hasattr(self, 'search_executor'):
            self.search_executor.shutdown(wait=False)

if __name__ == "__main__":
    app = App()
    app.mainloop()