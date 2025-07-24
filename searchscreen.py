import customtkinter as ctk
from PIL import Image, ImageTk
import requests
from io import BytesIO

class SearchScreen(ctk.CTkFrame):
    def __init__(self, parent, results, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.results = results
        
        # Configure grid weights
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Create main container with scrollbar
        self.canvas = ctk.CTkCanvas(self, bg="#1a1a1a", highlightthickness=0)
        self.scrollbar = ctk.CTkScrollbar(self, orientation="vertical", command=self.canvas.yview)
        self.scrollable_frame = ctk.CTkFrame(self.canvas, fg_color="transparent")
        
        # Configure canvas scrolling
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        # Create window in canvas for the scrollable frame
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Pack canvas and scrollbar
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        
        # Bind mousewheel for scrolling
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
        # Create results
        self.create_results_list()
    
    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def create_results_list(self):
        for idx, result in enumerate(self.results):
            # Download thumbnail image
            try:
                response = requests.get(result['thumbnail_url'])
                img_data = response.content
                image = Image.open(BytesIO(img_data)).resize((120, 80), Image.LANCZOS)
                tk_image = ctk.CTkImage(light_image=image, dark_image=image, size=(120, 80))
            except Exception as e:
                print(f"Error loading thumbnail: {e}")
                tk_image = None

            # Row frame
            row = ctk.CTkFrame(self.scrollable_frame, fg_color="#222", corner_radius=8)
            row.pack(fill="x", padx=0, pady=6)

            # Thumbnail
            if tk_image:
                thumb = ctk.CTkLabel(row, image=tk_image, text="", width=120, height=80)
                thumb.image = tk_image  # Keep reference
                thumb.pack(side="left", padx=8, pady=8)
            else:
                thumb = ctk.CTkLabel(row, text="No Image", width=120, height=80)
                thumb.pack(side="left", padx=8, pady=8)

            # Title and other details
            text_frame = ctk.CTkFrame(row, fg_color="transparent")
            text_frame.pack(side="left", fill="both", expand=True, padx=(0, 10), pady=8)
            
            title = ctk.CTkLabel(
                text_frame, 
                text=result.get('title', 'No Title'),
                font=ctk.CTkFont(size=16, weight="bold"),
                anchor="w",
                justify="left"
            )
            title.pack(anchor="w")
            
            # Add uploader and other details if available
            if 'uploader' in result or 'duration' in result:
                details = f"{result.get('uploader', '')} • {result.get('duration', '')}"
                if details.strip():
                    detail_label = ctk.CTkLabel(
                        text_frame,
                        text=details,
                        font=ctk.CTkFont(size=12),
                        text_color="gray",
                        anchor="w"
                    )
                    detail_label.pack(anchor="w", pady=(2, 0))
            
            # Add view count if available
            if 'view_count' in result:
                views = ctk.CTkLabel(
                    text_frame,
                    text=result['view_count'],
                    font=ctk.CTkFont(size=12),
                    text_color="gray",
                    anchor="w"
                )
                views.pack(anchor="w", pady=(2, 0))
