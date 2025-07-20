import customtkinter as ctk
from homescreen import HomeScreen
import datetime
import webbrowser

class MainScreen(ctk.CTkFrame):
    def __init__(self, master, switch_to_home_callback):
        super().__init__(master, fg_color="#121212")
        self.pack(fill="both", expand=True, padx=20, pady=20)
        self.switch_to_home_callback = switch_to_home_callback
        self.build_ui()

    def build_ui(self):
        # Search bar (styled like HomeScreen) - always on top
        self.search_var = ctk.StringVar()
        search_entry = ctk.CTkEntry(
            self,
            textvariable=self.search_var,
            width=400,
            placeholder_text="Search for music..."
        )
        search_entry.pack(pady=(10, 30), anchor="n")
        search_entry.bind("<KeyRelease>", self.on_search_input)

        # Greeting based on time
        now = datetime.datetime.now().hour
        if 5 <= now < 12:
            greeting = "Good morning, user!"
        elif 12 <= now < 18:
            greeting = "Good afternoon, user!"
        elif 18 <= now < 22:
            greeting = "Good evening, user!"
        else:
            greeting = "Hello, user!"

        greeting_label = ctk.CTkLabel(self, text=greeting, font=("Helvetica", 32, "bold"), text_color="#1DB954")
        greeting_label.pack(pady=(0, 10), anchor="n")

        # Suggestion label
        suggestion_label = ctk.CTkLabel(self, text="Try these trending playlists:", font=("Helvetica", 20, "bold"), text_color="#FFFFFF")
        suggestion_label.pack(pady=(10, 10), anchor="n")

        # Playlist suggestions (from web search)
        playlists = [
            ("Top Hits 2025 - Playlist", "https://www.youtube.com/playlist?list=PLDIoUOhQQPlXr63I_vwF9GD8sAKh77dWU"),
            ("Popular Music Videos 2025", "https://www.youtube.com/playlist?list=PLTmaZB7buLocCCFf2sx8Q72W7seIIrWbP"),
            ("Best Music 2025 - Latest Top Songs", "https://www.youtube.com/playlist?list=PL3oW2tjiIxvQ1BZS58qtot3-p-lD32oWT"),
            ("2025 Songs Playlist - Top Most Played", "https://www.youtube.com/playlist?list=PLx0sYbCqOb8RH0wzPsjeXyXMmQlMLMsQY"),
            ("Road Trip Songs 2025", "https://www.youtube.com/playlist?list=PLssZy5BJs9BfZZ_qlKCY-S5alrRLAnu9R"),
            ("Top hits 2024 playlist", "https://www.youtube.com/watch?v=U0ZoqmyGJo8&pp=0gcJCdgAo7VqN5tD"),
        ]

        for title, url in playlists:
            btn = ctk.CTkButton(
                self,
                text=title,
                fg_color="#1DB954",
                hover_color="#1ED760",
                text_color="#FFFFFF",
                font=("Helvetica", 16),
                corner_radius=8,
                command=lambda u=url: webbrowser.open(u)
            )
            btn.pack(pady=6, ipadx=10, ipady=4, anchor="n")

    def on_search_input(self, event=None):
        query = self.search_var.get().strip()
        if hasattr(self, 'search_timer') and self.search_timer:
            self.after_cancel(self.search_timer)
        if query:
            self.search_timer = self.after(800, lambda: self.switch_to_home_callback(query))
