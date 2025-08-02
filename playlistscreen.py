import customtkinter as ctk
import threading
import yt_dlp
from searchscreen import SearchScreen
from FirebaseClass import FirebaseManager


class PlaylistScreen(ctk.CTkFrame):
    def __init__(self, parent, current_user, on_song_selected_callback=None):
        super().__init__(parent, fg_color="transparent")
        self.current_user = current_user
        self.on_song_selected_callback = on_song_selected_callback
        self.search_screen = None
        
        # Configure yt-dlp options for fetching song details
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'no_check_certificate': True,
            'ignoreerrors': True,
            'geo_bypass': True,
            'noplaylist': True,
            'skip_download': True,
            'socket_timeout': 10,
            'retries': 1,
        }
        
        self.show_saved_songs_with_banner()
    
    def show_saved_songs_with_banner(self):
        """Show saved songs with a banner at the top"""
        if not self.current_user:
            return
        
        # Clear main frame
        for widget in self.winfo_children():
            widget.destroy()
        
        # Create container for banner and content
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Add banner at the top
        banner_frame = ctk.CTkFrame(container, fg_color="#1DB954", corner_radius=15, height=150)
        banner_frame.pack(fill="x", pady=(0, 20))
        banner_frame.pack_propagate(False)  # Prevent resizing
        
        # Banner content
        banner_content = ctk.CTkFrame(banner_frame, fg_color="transparent")
        banner_content.place(relx=0.5, rely=0.5, anchor="center")
        
        # Banner icon
        banner_icon = ctk.CTkLabel(
            banner_content,
            text="🎵",
            font=ctk.CTkFont(size=48),
            text_color="#FFFFFF"
        )
        banner_icon.pack(pady=(0, 10))
        
        # Banner title
        banner_title = ctk.CTkLabel(
            banner_content,
            text="Saved Songs",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#FFFFFF"
        )
        banner_title.pack(pady=(0, 5))
        
        # Banner subtitle with song count
        firebase = FirebaseManager()
        song_count = firebase.get_saved_songs_count(self.current_user)
        banner_subtitle = ctk.CTkLabel(
            banner_content,
            text=f"{song_count} song{'s' if song_count != 1 else ''}",
            font=ctk.CTkFont(size=16),
            text_color="#FFFFFF"
        )
        banner_subtitle.pack()
        
        # Get liked songs from Firebase
        liked_urls = firebase.get_user_liked_songs(self.current_user)
        
        if not liked_urls:
            # Show empty state
            empty_frame = ctk.CTkFrame(container, fg_color="#1a1a1a", corner_radius=10)
            empty_frame.pack(fill="both", expand=True, pady=10)
            
            empty_icon = ctk.CTkLabel(
                empty_frame,
                text="🎵",
                font=ctk.CTkFont(size=64),
                text_color="#1DB954"
            )
            empty_icon.pack(pady=(40, 20))
            
            empty_title = ctk.CTkLabel(
                empty_frame,
                text="No saved songs yet",
                font=ctk.CTkFont(size=20, weight="bold"),
                text_color="#FFFFFF"
            )
            empty_title.pack(pady=(0, 10))
            
            empty_subtitle = ctk.CTkLabel(
                empty_frame,
                text="Search for songs and like them to see them here!",
                font=ctk.CTkFont(size=16),
                text_color="#888888"
            )
            empty_subtitle.pack()
            return
        
        # Show loading state while fetching song details
        self.show_loading_state(container)
        
        # Fetch song details in background thread
        threading.Thread(
            target=self.fetch_song_details_from_urls,
            args=(liked_urls, container),
            daemon=True
        ).start()
    
    def show_loading_state(self, container):
        """Show loading state while fetching song details"""
        # Clear container content
        for widget in container.winfo_children():
            if widget != container.winfo_children()[0]:  # Keep banner
                widget.destroy()
        
        # Create loading frame
        loading_frame = ctk.CTkFrame(container, fg_color="#1a1a1a", corner_radius=10)
        loading_frame.pack(fill="both", expand=True, pady=10)
        
        # Loading icon
        loading_icon = ctk.CTkLabel(
            loading_frame,
            text="⏳",
            font=ctk.CTkFont(size=64),
            text_color="#1DB954"
        )
        loading_icon.pack(pady=(40, 20))
        
        # Loading text
        loading_text = ctk.CTkLabel(
            loading_frame,
            text="Loading your saved songs...",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#FFFFFF"
        )
        loading_text.pack(pady=(0, 10))
        
        # Subtitle
        loading_subtitle = ctk.CTkLabel(
            loading_frame,
            text="Fetching song details from YouTube",
            font=ctk.CTkFont(size=16),
            text_color="#888888"
        )
        loading_subtitle.pack()
    
    def fetch_song_details_from_urls(self, urls, container):
        """Fetch song details from YouTube URLs in background thread"""
        try:
            liked_songs = []
            
            for url in urls:
                try:
                    # Extract video ID from URL
                    if "youtube.com/watch?v=" in url:
                        video_id = url.split("v=")[1].split("&")[0]
                        
                        # Fetch song details using yt-dlp
                        with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                            info = ydl.extract_info(url, download=False)
                            
                            if info:
                                # Format duration
                                duration = info.get('duration', 0)
                                if duration:
                                    minutes = duration // 60
                                    seconds = duration % 60
                                    duration_str = f"{minutes}:{seconds:02d}"
                                else:
                                    duration_str = "0:00"
                                
                                # Format view count
                                view_count = info.get('view_count', 0)
                                if view_count:
                                    if view_count >= 1000000:
                                        view_str = f"{view_count // 1000000}M views"
                                    elif view_count >= 1000:
                                        view_str = f"{view_count // 1000}K views"
                                    else:
                                        view_str = f"{view_count} views"
                                else:
                                    view_str = "0 views"
                                
                                liked_songs.append({
                                    'videoId': video_id,
                                    'title': info.get('title', f'Unknown Title ({video_id})'),
                                    'uploader': info.get('uploader', 'Unknown'),
                                    'duration': duration_str,
                                    'view_count': view_str,
                                    'thumbnail_url': f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
                                    'url': url
                                })
                            else:
                                # Fallback to basic info if yt-dlp fails
                                liked_songs.append({
                                    'videoId': video_id,
                                    'title': f"Liked Song ({video_id})",
                                    'uploader': 'Unknown',
                                    'duration': '0:00',
                                    'view_count': '0 views',
                                    'thumbnail_url': f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
                                    'url': url
                                })
                
                except Exception as e:
                    print(f"Error fetching details for {url}: {str(e)}")
                    # Add basic info as fallback
                    if "youtube.com/watch?v=" in url:
                        video_id = url.split("v=")[1].split("&")[0]
                        liked_songs.append({
                            'videoId': video_id,
                            'title': f"Liked Song ({video_id})",
                            'uploader': 'Unknown',
                            'duration': '0:00',
                            'view_count': '0 views',
                            'thumbnail_url': f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
                            'url': url
                        })
            
            # Update UI in main thread
            self.after(0, lambda: self.display_saved_songs(liked_songs, container))
            
        except Exception as e:
            print(f"Error fetching song details: {str(e)}")
            self.after(0, lambda: self.show_saved_songs_error(container))
    
    def display_saved_songs(self, liked_songs, container):
        """Display the fetched saved songs"""
        # Clear loading state
        for widget in container.winfo_children():
            if widget != container.winfo_children()[0]:  # Keep banner
                widget.destroy()
        
        if not liked_songs:
            # Show empty state
            empty_frame = ctk.CTkFrame(container, fg_color="#1a1a1a", corner_radius=10)
            empty_frame.pack(fill="both", expand=True, pady=10)
            
            empty_icon = ctk.CTkLabel(
                empty_frame,
                text="🎵",
                font=ctk.CTkFont(size=64),
                text_color="#1DB954"
            )
            empty_icon.pack(pady=(40, 20))
            
            empty_title = ctk.CTkLabel(
                empty_frame,
                text="No saved songs found",
                font=ctk.CTkFont(size=20, weight="bold"),
                text_color="#FFFFFF"
            )
            empty_title.pack(pady=(0, 10))
            
            empty_subtitle = ctk.CTkLabel(
                empty_frame,
                text="Try refreshing or check your liked songs",
                font=ctk.CTkFont(size=16),
                text_color="#888888"
            )
            empty_subtitle.pack()
            return
        
        # Display liked songs using SearchScreen
        self.search_screen = SearchScreen(container, liked_songs, None, self.current_user)
        self.search_screen.pack(fill="both", expand=True)
        
        if self.on_song_selected_callback:
            self.search_screen.set_song_selection_callback(self.on_song_selected_callback)
    
    def show_saved_songs_error(self, container):
        """Show error state when fetching song details fails"""
        # Clear loading state
        for widget in container.winfo_children():
            if widget != container.winfo_children()[0]:  # Keep banner
                widget.destroy()
        
        # Create error frame
        error_frame = ctk.CTkFrame(container, fg_color="#1a1a1a", corner_radius=10)
        error_frame.pack(fill="both", expand=True, pady=10)
        
        # Error icon
        error_icon = ctk.CTkLabel(
            error_frame,
            text="⚠️",
            font=ctk.CTkFont(size=64),
            text_color="#FF6B6B"
        )
        error_icon.pack(pady=(40, 20))
        
        # Error title
        error_title = ctk.CTkLabel(
            error_frame,
            text="Failed to load saved songs",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#FFFFFF"
        )
        error_title.pack(pady=(0, 10))
        
        # Error subtitle
        error_subtitle = ctk.CTkLabel(
            error_frame,
            text="Please check your internet connection and try again",
            font=ctk.CTkFont(size=16),
            text_color="#888888"
        )
        error_subtitle.pack(pady=(0, 20))
        
        # Retry button
        retry_btn = ctk.CTkButton(
            error_frame,
            text="Retry",
            font=ctk.CTkFont(size=16),
            fg_color="#1DB954",
            hover_color="#1ed760",
            command=lambda: self.show_saved_songs_with_banner()
        )
        retry_btn.pack()
