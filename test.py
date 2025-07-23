import customtkinter as ctk
from PIL import Image, ImageTk
import os
from youtubesearchpython import VideosSearch
from searchscreen import SearchScreen
import threading

# Setup
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue") 

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("HanyaMusic")
        self.geometry("1920x1080")
        self.resizable(False, False)

        # State
        self.menu_visible = False

        # Layout containers
        self.create_topbar()
        self.create_main_area()

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
            width=550,  # Slightly reduced to fit 'X'
            height=36,
            font=search_font,
            corner_radius=10
        )
        self.searchbar.place(x=48, y=2)
        self.searchbar.bind('<Return>', self.on_search)
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

    def load_search_icon(self):
        icon_path = os.path.join("public", "icon", "search.png")  # your magnifying glass icon
        image = Image.open(icon_path)
        image = image.resize((24, 24), Image.LANCZOS)
        return ctk.CTkImage(light_image=image, dark_image=image, size=(24, 24))

    def load_user_icon(self):
        icon_path = os.path.join("public", "icon", "profile.png")
        image = Image.open(icon_path)
        image = image.resize((40, 40), Image.LANCZOS)
        return ctk.CTkImage(light_image=image, dark_image=image, size=(40, 40))

    def create_main_area(self):
        self.main_frame = ctk.CTkFrame(self, fg_color="black")
        self.main_frame.place(x=0, y=60, relwidth=1, relheight=1, anchor="nw")

    def on_search(self, event=None):
        query = self.searchbar.get().strip()
        if not query:
            return
        # Show loading indicator
        self.show_loading()
        # Start search in a background thread
        threading.Thread(target=self.perform_search, args=(query,), daemon=True).start()

    def show_loading(self):
        # Clear main_frame
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        self.loading_label = ctk.CTkLabel(self.main_frame, text="Searching...", font=ctk.CTkFont(size=24))
        self.loading_label.pack(pady=40)

    def perform_search(self, query):
        try:
            videos_search = VideosSearch(query)
            results = []
            for v in videos_search.result().get('result', []):
                results.append({
                    'title': v.get('title', 'No Title'),
                    'thumbnail_url': v.get('thumbnails', [{}])[0].get('url', ''),
                    'videoId': v.get('id', '')
                })
        except Exception as e:
            results = []
        # Update UI on main thread
        self.after(0, self.display_results, results)

    def display_results(self, results):
        # Clear main_frame
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        if not results:
            label = ctk.CTkLabel(self.main_frame, text="No results found or error occurred.", font=ctk.CTkFont(size=18))
            label.pack(pady=40)
            return
        search_screen = SearchScreen(self.main_frame, results)
        search_screen.pack(fill="both", expand=True)

if __name__ == "__main__":
    app = App()
    app.mainloop()
