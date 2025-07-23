import customtkinter as ctk
from PIL import Image, ImageTk
import requests
from io import BytesIO

class SearchScreen(ctk.CTkFrame):
    def __init__(self, parent, results, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.results = results
        self.create_results_list()

    def create_results_list(self):
        for idx, result in enumerate(self.results):
            # Download thumbnail image
            try:
                response = requests.get(result['thumbnail_url'])
                img_data = response.content
                image = Image.open(BytesIO(img_data)).resize((80, 80), Image.LANCZOS)
                tk_image = ctk.CTkImage(light_image=image, dark_image=image, size=(80, 80))
            except Exception:
                tk_image = None

            # Row frame
            row = ctk.CTkFrame(self, fg_color="#222", corner_radius=8)
            row.pack(fill="x", padx=10, pady=6)

            # Thumbnail
            if tk_image:
                thumb = ctk.CTkLabel(row, image=tk_image, text="", width=80, height=80)
                thumb.image = tk_image  # Keep reference
                thumb.pack(side="left", padx=8, pady=8)
            else:
                thumb = ctk.CTkLabel(row, text="No Image", width=80, height=80)
                thumb.pack(side="left", padx=8, pady=8)

            # Title
            title = ctk.CTkLabel(row, text=result['title'], font=ctk.CTkFont(size=18), anchor="w")
            title.pack(side="left", fill="x", expand=True, padx=8)
