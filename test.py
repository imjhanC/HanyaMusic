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
from FirebaseClass import FirebaseManager
from datetime import datetime
from BannerAnimationClass import AnimatedBanner
from SessionManagerClass import SessionManager

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
        self.side_menu_visible = False
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
        self.session_manager = SessionManager()  # Initialize session manager
        
        # Layout containers
        self.create_main_area()  # Create main frame first
        self.create_topbar()
        self.create_music_player_area()
        self.create_side_menu()  # Create sidebar last so it appears on top
        
        # Bind window events
        self.bind('<Configure>', self._on_window_configure)
        
        # Check for existing session and auto-login
        self.after(100, self.check_existing_session)
        
        # Show the welcome banner when app starts
        self.show_main_frame()

    def create_side_menu(self):
        """Create the side menu that slides in from the left"""
        # Side menu container
        self.side_menu = ctk.CTkFrame(
            self,
            width=300,
            fg_color="#0f0f0f",
            corner_radius=0
        )
        
        # Initially hide the side menu off-screen to the left
        # Use relheight=1.0 and rely=0 to make it fill the entire window height
        self.side_menu.place(relx=-0.3, rely=0, relwidth=0.3, relheight=1.0, anchor="nw")
        
        # Create side menu content
        self.create_side_menu_content()
    
    def create_side_menu_content(self):
        """Create the content for the side menu"""
        # Header
        header_frame = ctk.CTkFrame(self.side_menu, fg_color="transparent", height=80)
        header_frame.pack(fill="x", padx=20, pady=20)
        header_frame.pack_propagate(False)
        
        # Close button (←) at upper right corner
        close_btn = ctk.CTkButton(
            header_frame,
            text="←",
            width=40,
            height=40,
            corner_radius=20,
            fg_color="transparent",
            hover_color="#333333",
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=20),
            command=self.toggle_side_menu
        )
        close_btn.pack(side="right")
        
        # Title
        title_label = ctk.CTkLabel(
            header_frame,
            text="Menu",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#FFFFFF"
        )
        title_label.pack(side="left", pady=20)
        
        # Menu items container
        menu_items_frame = ctk.CTkFrame(self.side_menu, fg_color="transparent")
        menu_items_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Menu items
        menu_items = [
            ("🏠 Home", self.on_home_clicked),
            ("⚙️ Settings", self.on_settings_clicked),
            ("ℹ️ About", self.on_about_clicked),
            ("📞 Contact", self.on_contact_clicked),
        ]
        
        for text, command in menu_items:
            btn = ctk.CTkButton(
                menu_items_frame,
                text=text,
                font=ctk.CTkFont(size=16),
                fg_color="transparent",
                hover_color="#333333",
                anchor="w",
                command=command,
                height=50
            )
            btn.pack(fill="x", pady=5)
        
        # Bottom section
        bottom_frame = ctk.CTkFrame(self.side_menu, fg_color="transparent")
        bottom_frame.pack(fill="x", padx=20, pady=20)
        
        # User info
        if self.logged_in:
            user_info = ctk.CTkLabel(
                bottom_frame,
                text=f"Logged in as: {self.current_user}",
                font=ctk.CTkFont(size=14),
                text_color="#1DB954"
            )
            user_info.pack(pady=10)
            
            # Logout button
            logout_btn = ctk.CTkButton(
                bottom_frame,
                text="Log Out",
                font=ctk.CTkFont(size=14),
                fg_color="#FF6B6B",
                hover_color="#FF5252",
                command=self.on_side_menu_logout_clicked  # Use the new method
            )
            logout_btn.pack(fill="x", pady=5)
        else:
            login_btn = ctk.CTkButton(
                bottom_frame,
                text="Log In",
                font=ctk.CTkFont(size=14),
                fg_color="#1DB954",
                hover_color="#1ed760",
                command=self.on_side_menu_login_clicked  # Use the new method
            )
            login_btn.pack(fill="x", pady=5)
    
    def toggle_side_menu(self):
        """Toggle the side menu visibility"""
        if self.side_menu_visible:
            self.hide_side_menu()
        else:
            self.show_side_menu()
    
    def show_side_menu(self):
        """Show the side menu with animation"""
        self.side_menu_visible = True
        
        # Bring sidebar to front so it overlays the main frame
        self.side_menu.lift()
        
        # Position the menu off-screen initially, using full height
        self.side_menu.place(relx=-0.3, rely=0, relwidth=0.2, relheight=1.0, anchor="nw")
        
        # Animate the menu sliding in
        def animate_in(progress=0):
            if progress <= 1.0 and self.side_menu_visible:
                # Calculate position based on progress (-0.3 to 0.0)
                relx = -0.3 + (0.3 * progress)
                self.side_menu.place(relx=relx, rely=0, relwidth=0.2, relheight=1.0, anchor="nw")
                if progress < 1.0:
                    self.after(10, lambda: animate_in(progress + 0.1))
        
        animate_in()
    
    def hide_side_menu(self):
        """Hide the side menu with animation"""
        self.side_menu_visible = False
        
        # Animate the menu sliding out
        def animate_out(progress=0):
            if progress <= 1.0 and not self.side_menu_visible:
                # Calculate position based on progress (0.0 to -0.3)
                relx = -0.3 + (0.3 * (1 - progress))
                self.side_menu.place(relx=relx, rely=0, relwidth=0.2, relheight=1.0, anchor="nw")
                if progress < 1.0:
                    self.after(10, lambda: animate_out(progress + 0.1))
                else:
                    # Hide completely when animation is done
                    self.side_menu.place_forget()
        
        animate_out()
        
    def on_home_clicked(self):
        """Handle home menu item click"""
        self.hide_side_menu()
        self.show_main_frame()
        print("Home clicked")

    def on_settings_clicked(self):
        """Handle settings menu item click"""
        self.hide_side_menu()
        print("Settings clicked")
        # Add settings functionality here
    
    def on_about_clicked(self):
        """Handle about menu item click"""
        self.hide_side_menu()
        print("About clicked")
        # Add about dialog here
    
    def on_contact_clicked(self):
        """Handle contact menu item click"""
        self.hide_side_menu()
        print("Contact clicked")
        # Add contact functionality here

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
        
        # Hamburger menu button (left side)
        self.hamburger_btn = ctk.CTkButton(
            self,
            text="☰",
            width=40,
            height=40,
            corner_radius=20,
            fg_color="transparent",
            hover_color="#333333",
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=20),
            command=self.toggle_side_menu
        )
        self.hamburger_btn.place(x=20, y=10)
        
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
        """Handle login menu item click from user menu"""
        # Only hide user menu, not side menu
        self.hide_user_menu()
        
        # Create and show login window
        login_window = LoginWindow(self, on_login_success=self.on_login_success)
        # Set focus to the login window
        login_window.focus_force()
    
    def on_side_menu_login_clicked(self):
        """Handle login button click from side menu"""
        # Only hide side menu, not user menu
        self.hide_side_menu()
        
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
        
        # Update side menu content
        self.update_side_menu_content()
        
        # Refresh the playlist section to show playlists instead of login prompt
        self.refresh_playlist_section()

    def on_logout_clicked(self):
        """Handle logout menu item click from user menu"""
        self.hide_user_menu()
        
        # Clear session
        self.session_manager.clear_session()
        
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
        
        # Update side menu content
        self.update_side_menu_content()
        
        # Refresh the playlist section to show login prompt
        self.refresh_playlist_section()
        
        print("User logged out and session cleared")

    def on_side_menu_logout_clicked(self):
        """Handle logout button click from side menu"""
        self.hide_side_menu()
        
        # Clear session
        self.session_manager.clear_session()
        
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
        
        # Update side menu content
        self.update_side_menu_content()
        
        # Refresh the playlist section to show login prompt
        self.refresh_playlist_section()
        
        print("User logged out and session cleared")

    def update_side_menu_content(self):
        """Update the side menu content based on login status"""
        # Clear existing content
        for widget in self.side_menu.winfo_children():
            widget.destroy()
        
        # Recreate content
        self.create_side_menu_content()

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
        """Enhanced show_main_frame with animated banner"""
        # Clear main_frame and recreate it
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        
        # Recreate main frame
        self.main_frame = ctk.CTkFrame(self, fg_color="black")
        self.main_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=(60, 0))
        
        # Create container for banner and content
        container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Add animated banner
        banner = AnimatedBanner(
            container,
            height=200,
            corner_radius=15,
            fg_color="transparent"
        )
        banner.pack(fill="x", pady=(0, 20))
        
        # Add welcome content below banner
        welcome_frame = ctk.CTkFrame(container, fg_color="#1a1a1a", corner_radius=10)
        welcome_frame.pack(fill="x", pady=10)
        
        # Add playlist section
        self.create_playlist_section(welcome_frame)
        

    def create_playlist_section(self, parent_frame):
        """Create the playlist cards section"""
        # Check if user is logged in
        if not self.logged_in:
            # Show login prompt when not logged in
            self.create_login_prompt(parent_frame)
            return
        
        # Initialize playlists if not exists
        if not hasattr(self, 'playlists'):
            self.playlists = [
                {"name": "Saved Songs", "songs": [], "is_default": True}
            ]
            self.next_playlist_number = 1
        
        # Playlist section header
        header_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(20, 10))
        
        # Title
        title_label = ctk.CTkLabel(
            header_frame,
            text="Your Playlists",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#1DB954"
        )
        title_label.pack(side="left")
        
        # Add playlist button
        add_btn = ctk.CTkButton(
            header_frame,
            text="+ New Playlist",
            font=ctk.CTkFont(size=14),
            fg_color="#1DB954",
            hover_color="#1ed760",
            command=self.add_new_playlist,
            width=120,
            height=32
        )
        add_btn.pack(side="right")
        
        # Playlist cards container - store reference for smooth refresh
        self.playlist_cards_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        self.playlist_cards_frame.pack(fill="x", padx=20, pady=(0, 10))
        
        # Create playlist cards
        self.create_playlist_cards(self.playlist_cards_frame)

    def create_login_prompt(self, parent_frame):
        """Create a login prompt when user is not logged in"""
        # Create transparent container for login prompt with fixed height
        login_container = ctk.CTkFrame(parent_frame, fg_color="transparent", height=220)
        login_container.pack(fill="x", padx=20, pady=10)
        login_container.pack_propagate(False)  # Prevent resizing
        
        # Center the login prompt
        login_frame = ctk.CTkFrame(login_container, fg_color="transparent")
        login_frame.place(relx=0.5, rely=0.5, anchor="center")
        
        # Login icon
        login_icon = ctk.CTkLabel(
            login_frame,
            text="🔐",
            font=ctk.CTkFont(size=48),
            text_color="#1DB954"
        )
        login_icon.pack(pady=(0, 20))
        
        # Login message
        login_message = ctk.CTkLabel(
            login_frame,
            text="Please log in to access this feature",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#FFFFFF"
        )
        login_message.pack(pady=(0, 15))
        
        # Subtitle
        subtitle = ctk.CTkLabel(
            login_frame,
            text="Create and manage your playlists",
            font=ctk.CTkFont(size=14),
            text_color="#888888"
        )
        subtitle.pack(pady=(0, 25))
        
        # Login button
        login_btn = ctk.CTkButton(
            login_frame,
            text="Log In",
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="#1DB954",
            hover_color="#1ed760",
            command=self.on_login_clicked,
            width=120,
            height=40
        )
        login_btn.pack()
    
    def refresh_playlist_cards(self):
        """Smoothly refresh only the playlist cards without affecting the banner"""
        if hasattr(self, 'playlist_cards_frame'):
            if self.logged_in:
                self.create_playlist_cards(self.playlist_cards_frame)
            else:
                # Clear the frame and show login prompt
                for widget in self.playlist_cards_frame.winfo_children():
                    widget.destroy()
                self.create_login_prompt(self.playlist_cards_frame.master)

    def create_playlist_cards(self, parent_frame):
        """Create individual playlist cards"""
        # Clear existing cards
        for widget in parent_frame.winfo_children():
            widget.destroy()
        
        # Create a horizontal scrollable frame for cards
        canvas = ctk.CTkCanvas(parent_frame, bg="#1a1a1a", highlightthickness=0)
        scrollbar = ctk.CTkScrollbar(parent_frame, orientation="horizontal", command=canvas.xview)
        scrollable_frame = ctk.CTkFrame(canvas, fg_color="transparent")
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(xscrollcommand=scrollbar.set)
        
        # Pack canvas and scrollbar
        canvas.pack(side="top", fill="x", expand=False)
        scrollbar.pack(side="bottom", fill="x")
        
        # Create cards in a single row layout
        for i, playlist in enumerate(self.playlists):
            # Create playlist card
            card = self.create_playlist_card(scrollable_frame, playlist, i)
            card.pack(side="left", padx=10, pady=10)
        
        # Update scroll region and check if scrollbar is needed
        def update_scroll_region():
            canvas.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))
            
            # Check if content is wider than canvas
            content_width = scrollable_frame.winfo_reqwidth()
            canvas_width = canvas.winfo_width()
            
            if content_width > canvas_width:
                # Show scrollbar only when needed
                scrollbar.pack(side="bottom", fill="x")
            else:
                # Hide scrollbar when not needed
                scrollbar.pack_forget()
        
        # Bind mouse wheel to horizontal scroll with bounds checking
        def _on_mousewheel(event):
            # Get current scroll position
            current_pos = canvas.xview()[0]
            
            # Calculate scroll amount
            scroll_amount = int(-1*(event.delta/120))
            
            # Only allow scrolling right (positive) when at the beginning
            if current_pos <= 0 and scroll_amount < 0:
                return
            
            # Only allow scrolling left (negative) when not at the end
            if current_pos >= 1 and scroll_amount > 0:
                return
            
            canvas.xview_scroll(scroll_amount, "units")
        
        # Update scroll region after a short delay to ensure proper sizing
        canvas.after(100, update_scroll_region)
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
    
    def create_playlist_card(self, parent, playlist, index):
        """Create a single playlist card"""
        card = ctk.CTkFrame(parent, fg_color="#2a2a2a", corner_radius=10, height=220, width=200)
        card.pack_propagate(False)
        
        # Card content
        content_frame = ctk.CTkFrame(card, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Playlist icon
        icon_label = ctk.CTkLabel(
            content_frame,
            text="🎵" if playlist["is_default"] else "📁",
            font=ctk.CTkFont(size=40),
            text_color="#1DB954" if playlist["is_default"] else "#FFFFFF"
        )
        icon_label.pack(pady=(0, 15))
        
        # Playlist name and edit button container
        name_container = ctk.CTkFrame(content_frame, fg_color="transparent")
        name_container.pack(fill="x", pady=(0, 8))
        
        # Playlist name
        name_label = ctk.CTkLabel(
            name_container,
            text=playlist["name"],
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#FFFFFF"
        )
        name_label.pack(side="left", fill="x", expand=True)
        
        # Edit button (only for non-default playlists)
        if not playlist["is_default"]:
            edit_btn = ctk.CTkButton(
                name_container,
                text="✏",
                width=25,
                height=25,
                font=ctk.CTkFont(size=12),
                fg_color="#444444",
                hover_color="#555555",
                command=lambda: self.start_inline_edit(card, playlist, index)
            )
            edit_btn.pack(side="right", padx=(5, 0))
        
        # Song count - use Firebase for "Saved Songs", local count for other playlists
        if playlist["is_default"] and self.logged_in:
            # Get count from Firebase for "Saved Songs"
            firebase = FirebaseManager()
            song_count = firebase.get_saved_songs_count(self.current_user)
        else:
            # Use local count for other playlists
            song_count = len(playlist["songs"])
        
        count_label = ctk.CTkLabel(
            content_frame,
            text=f"{song_count} song{'s' if song_count != 1 else ''}",
            font=ctk.CTkFont(size=14),
            text_color="#888888"
        )
        count_label.pack(pady=(0, 15))
        
        # Action buttons
        button_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        button_frame.pack(fill="x")
        
        # Play button
        play_btn = ctk.CTkButton(
            button_frame,
            text="▶",
            width=35,
            height=35,
            font=ctk.CTkFont(size=16),
            fg_color="#1DB954",
            hover_color="#1ed760",
            command=lambda: self.play_playlist(index)
        )
        play_btn.pack(side="left", padx=(0, 8))
        
        # Delete button (only for non-default playlists)
        if not playlist["is_default"]:
            delete_btn = ctk.CTkButton(
                button_frame,
                text="🗑",
                width=35,
                height=35,
                font=ctk.CTkFont(size=16),
                fg_color="#FF6B6B",
                hover_color="#FF5252",
                command=lambda: self.delete_playlist(index)
            )
            delete_btn.pack(side="left")
        
        # Add double-click functionality for "Saved Songs" playlist
        if playlist["is_default"] and self.logged_in:
            card.bind("<Double-Button-1>", lambda event: self.show_saved_songs_playlist())
        
        return card

    def show_saved_songs_playlist(self):
        """Show saved songs playlist using PlaylistScreen"""
        if not self.logged_in:
            return
        
        # Clear main frame
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        
        # Create and display PlaylistScreen
        from playlistscreen import PlaylistScreen
        self.playlist_screen = PlaylistScreen(self.main_frame, self.current_user, self.on_song_selected)
        self.playlist_screen.pack(fill="both", expand=True)

    def start_inline_edit(self, card, playlist, index):
        """Start inline editing of playlist name"""
        # Find the name container in the card
        content_frame = card.winfo_children()[0]  # Get the content frame
        name_container = None
        
        # Find the name container
        for widget in content_frame.winfo_children():
            if isinstance(widget, ctk.CTkFrame) and len(widget.winfo_children()) > 0:
                if isinstance(widget.winfo_children()[0], ctk.CTkLabel):
                    name_container = widget
                    break
        
        if not name_container:
            return
        
        # Clear the name container
        for widget in name_container.winfo_children():
            widget.destroy()
        
        # Create entry field
        entry = ctk.CTkEntry(
            name_container,
            font=ctk.CTkFont(size=18, weight="bold"),
            fg_color="#333333",
            text_color="#FFFFFF",
            border_color="#1DB954",
            border_width=2
        )
        entry.pack(side="left", fill="x", expand=True)
        entry.insert(0, playlist["name"])
        entry.select_range(0, 'end')
        entry.focus_set()
        
        # Create save button
        save_btn = ctk.CTkButton(
            name_container,
            text="✓",
            width=80,
            height=25,
            font=ctk.CTkFont(size=16),
            fg_color="#1DB954",
            hover_color="#1ed760",
            command=lambda: self.save_inline_edit(card, playlist, index, entry)
        )
        save_btn.pack(side="right", padx=(3, 0))
        
        # Bind Enter key to save
        def on_enter(event):
            self.save_inline_edit(card, playlist, index, entry)
        
        entry.bind('<Return>', on_enter)
        
        # Bind Escape key to cancel
        def on_escape(event):
            self.cancel_inline_edit(card, playlist, index)
        
        entry.bind('<Escape>', on_escape)

    def save_inline_edit(self, card, playlist, index, entry):
        """Save the inline edit"""
        new_name = entry.get().strip()
        if new_name and new_name != playlist["name"]:
            playlist["name"] = new_name
            self.refresh_playlist_cards()
        else:
            # If no change or empty name, just cancel
            self.cancel_inline_edit(card, playlist, index)

    def cancel_inline_edit(self, card, playlist, index):
        """Cancel the inline edit and restore original name"""
        self.refresh_playlist_cards()
    
    def add_new_playlist(self):
        """Add a new playlist"""
        playlist_name = f"Playlist {self.next_playlist_number}"
        new_playlist = {
            "name": playlist_name,
            "songs": [],
            "is_default": False
        }
        self.playlists.append(new_playlist)
        self.next_playlist_number += 1
        
        # Smoothly refresh only the playlist cards
        self.refresh_playlist_cards()
    
    def edit_playlist_name(self, index):
        """Edit playlist name"""
        if index >= len(self.playlists) or self.playlists[index]["is_default"]:
            return
        
        # Create a simple dialog for editing
        dialog = ctk.CTkToplevel(self)
        dialog.title("Edit Playlist Name")
        dialog.geometry("300x150")
        dialog.resizable(False, False)
        
        # Center the dialog
        dialog.transient(self)
        dialog.grab_set()
        
        # Entry for new name
        entry = ctk.CTkEntry(
            dialog,
            placeholder_text="Enter playlist name",
            width=250
        )
        entry.pack(pady=20)
        entry.insert(0, self.playlists[index]["name"])
        entry.focus_set()
        
        # Buttons
        button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        button_frame.pack(pady=20)
        
        def save_name():
            new_name = entry.get().strip()
            if new_name:
                self.playlists[index]["name"] = new_name
                self.refresh_playlist_cards()
            dialog.destroy()
        
        def cancel():
            dialog.destroy()
        
        ctk.CTkButton(
            button_frame,
            text="Save",
            command=save_name,
            fg_color="#1DB954"
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            button_frame,
            text="Cancel",
            command=cancel,
            fg_color="#666666"
        ).pack(side="left", padx=5)
    
    def delete_playlist(self, index):
        """Delete a playlist"""
        if index >= len(self.playlists) or self.playlists[index]["is_default"]:
            return
        
        # Remove the playlist
        self.playlists.pop(index)
        
        # Smoothly refresh only the playlist cards
        self.refresh_playlist_cards()
    
    def play_playlist(self, index):
        """Play a playlist"""
        if index >= len(self.playlists):
            return
        
        playlist = self.playlists[index]
        if not playlist["songs"]:
            # Show empty playlist message
            print(f"Playlist '{playlist['name']}' is empty")
            return
        
        # Set current playlist and start playing
        self.current_playlist = playlist["songs"]
        self.current_song_index = 0
        
        # Show music player with first song
        if playlist["songs"]:
            first_song = playlist["songs"][0]
            self.on_song_selected(first_song, playlist["songs"], 0)
    
    def add_song_to_playlist(self, song_data, playlist_index=None):
        """Add a song to a playlist"""
        if playlist_index is None:
            # Add to "Saved Songs" (index 0)
            playlist_index = 0
        
        if playlist_index >= len(self.playlists):
            return False
        
        # Check if song already exists in playlist
        song_url = song_data.get('url', '')
        for existing_song in self.playlists[playlist_index]["songs"]:
            if existing_song.get('url') == song_url:
                print(f"Song already exists in playlist '{self.playlists[playlist_index]['name']}'")
                return False
        
        # Add song to playlist
        self.playlists[playlist_index]["songs"].append(song_data)
        print(f"Added song to playlist '{self.playlists[playlist_index]['name']}'")
        
        # Smoothly refresh only the playlist cards
        self.refresh_playlist_cards()
        return True
    
    def show_add_to_playlist_dialog(self, song_data):
        """Show dialog to choose which playlist to add song to"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Add to Playlist")
        dialog.geometry("400x300")
        dialog.resizable(False, False)
        
        # Center the dialog
        dialog.transient(self)
        dialog.grab_set()
        
        # Title
        title_label = ctk.CTkLabel(
            dialog,
            text="Choose a playlist:",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#FFFFFF"
        )
        title_label.pack(pady=20)
        
        # Create scrollable frame for playlist options
        canvas = ctk.CTkCanvas(dialog, bg="#1a1a1a", highlightthickness=0, height=200)
        scrollbar = ctk.CTkScrollbar(dialog, orientation="vertical", command=canvas.yview)
        scrollable_frame = ctk.CTkFrame(canvas, fg_color="transparent")
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True, padx=20)
        scrollbar.pack(side="right", fill="y", padx=(0, 20))
        
        # Create playlist options
        for i, playlist in enumerate(self.playlists):
            playlist_frame = ctk.CTkFrame(scrollable_frame, fg_color="#2a2a2a", corner_radius=5)
            playlist_frame.pack(fill="x", padx=10, pady=5)
            
            # Playlist info
            info_frame = ctk.CTkFrame(playlist_frame, fg_color="transparent")
            info_frame.pack(fill="x", padx=10, pady=5)
            
            name_label = ctk.CTkLabel(
                info_frame,
                text=playlist["name"],
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color="#FFFFFF"
            )
            name_label.pack(side="left")
            
            count_label = ctk.CTkLabel(
                info_frame,
                text=f"({len(playlist['songs'])} songs)",
                font=ctk.CTkFont(size=12),
                text_color="#888888"
            )
            count_label.pack(side="right")
            
            # Add button
            add_btn = ctk.CTkButton(
                playlist_frame,
                text="Add",
                font=ctk.CTkFont(size=12),
                fg_color="#1DB954",
                hover_color="#1ed760",
                command=lambda idx=i: self.add_song_to_playlist_and_close(song_data, idx, dialog),
                width=60,
                height=25
            )
            add_btn.pack(pady=(0, 5))
    
    def add_song_to_playlist_and_close(self, song_data, playlist_index, dialog):
        """Add song to playlist and close dialog"""
        success = self.add_song_to_playlist(song_data, playlist_index)
        if success:
            dialog.destroy()
            # Show success message
            self.show_success_message(f"Added to '{self.playlists[playlist_index]['name']}'")
    
    def show_success_message(self, message):
        """Show a temporary success message"""
        # Create a temporary message overlay
        msg_frame = ctk.CTkFrame(self, fg_color="#1DB954", corner_radius=10)
        msg_frame.place(relx=0.5, rely=0.1, anchor="center")
        
        msg_label = ctk.CTkLabel(
            msg_frame,
            text=message,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#FFFFFF"
        )
        msg_label.pack(padx=20, pady=10)
        
        # Auto-hide after 2 seconds
        self.after(2000, msg_frame.destroy)

    def clear_searchbar(self):
        # Check if search bar has content before clearing
        current_content = self.searchbar.get().strip()
        
        # Clear the search bar
        self.searchbar.delete(0, 'end')
        
        # Cancel any pending searches
        if self.after_id:
            self.after_cancel(self.after_id)
        if self.current_search_future and not self.current_search_future.done():
            self.current_search_future.cancel()
        
        # Only reload the screen if the search bar had content
        if current_content:
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
                'geo_bypass': True,
                'noplaylist': True,
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
            
        # Create search results screen with current user
        self.search_screen = SearchScreen(self.main_frame, results, self.load_more_results, self.current_user)
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
        # Only handle resize events for the main window, not child widgets
        if event.widget == self:
            if not self._resize_in_progress:
                self._resize_in_progress = True
                if self._resize_after_id:
                    self.after_cancel(self._resize_after_id)
                self._resize_after_id = self.after(100, self._process_resize)
    
    def _process_resize(self):
        """Process window resize - update menu position if visible"""
        self._resize_in_progress = False
        
        # Update user menu position if visible
        if self.user_menu_visible:
            self.update_user_menu_position()
        
        # Update sidebar position if visible (maintains its relative positioning automatically)
        # The sidebar will automatically adjust its height due to relheight=1.0
        if self.side_menu_visible:
            # Force update the sidebar position to ensure it stays properly positioned
            current_relx = self.side_menu.place_info().get('relx', '0')
            if current_relx:
                try:
                    relx_value = float(current_relx)
                    self.side_menu.place(relx=relx_value, rely=0, relwidth=0.2, relheight=1.0, anchor="nw")
                except (ValueError, TypeError):
                    pass
    
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

    def refresh_playlist_section(self):
        """Refresh the entire playlist section based on login status"""
        self.show_main_frame()

    def check_existing_session(self):
        """Check for existing session and auto-login if valid"""
        session = self.session_manager.get_saved_session()
        if session and 'username' in session:
            # Auto-login the user
            self.current_user = session['username']
            self.logged_in = True
            
            # Update UI to show logged in state
            self.username_label.configure(text=self.current_user)
            self.username_label.pack(side="left", padx=(0, 10))
            
            # Update menu items to show Log Out instead of Log In
            self.menu_items = [
                ("Log Out", self.on_logout_clicked),
                ("Settings", self.on_settings_clicked),
                ("About", self.on_about_clicked)
            ]
            
            # Recreate the menu with updated items
            self.create_user_menu()
            
            # Update side menu content
            self.update_side_menu_content()
            
            # Refresh the playlist section to show playlists
            self.refresh_playlist_section()
            
            print(f"Auto-logged in as {self.current_user}")

    def __del__(self):
        """Cleanup when app is destroyed"""
        if hasattr(self, 'search_executor'):
            self.search_executor.shutdown(wait=False)

if __name__ == "__main__":
    app = App()
    app.mainloop()