import customtkinter as ctk
from PIL import Image, ImageTk
import requests
from io import BytesIO

class SearchScreen(ctk.CTkFrame):
    def __init__(self, parent, results, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.results = results
        self.configure(fg_color="transparent")
        
        # Main container frame
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=0, pady=2)
        
        # Create scrollable canvas - remove fixed width
        self.canvas = ctk.CTkCanvas(
            self.main_container, 
            bg="#1a1a1a", 
            highlightthickness=0
            # Remove width parameter - let it size naturally
        )
        
        self.scrollbar = ctk.CTkScrollbar(
            self.main_container, 
            orientation="vertical", 
            command=self.canvas.yview
        )
        
        self.scrollable_frame = ctk.CTkFrame(
            self.canvas, 
            fg_color="transparent"
        )
        
        # Configure the canvas scrolling
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )
        
        # Pack scrollbar first, then canvas
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True, padx=0, pady=0)
        
        # Create window in canvas for the scrollable frame - let it size dynamically
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Bind mousewheel for scrolling
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
        # Bind canvas configure event to update scroll region and window width
        self.canvas.bind("<Configure>", self.on_canvas_configure)
        
        # Create results grid
        self.create_results_grid()
    
    def on_canvas_configure(self, event):
        # Update the scroll region
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        # Update the canvas window width to match canvas width
        self.canvas.itemconfig(self.canvas_window, width=event.width)
    
    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def create_results_grid(self):
        # Configure grid for scrollable frame
        self.scrollable_frame.columnconfigure(0, weight=1)
        
        # Create a frame for each result item
        for idx, result in enumerate(self.results):
            # Create card frame that will span the full width
            card = ctk.CTkFrame(
                self.scrollable_frame, 
                fg_color="#222222",
                corner_radius=10,
                height=100
            )
            # Make card expand to fill available width
            card.grid(row=idx, column=0, sticky="nsew", padx=15, pady=5)
            card.grid_columnconfigure(1, weight=1)  # Make the text area expandable
            
            # Download thumbnail image
            try:
                response = requests.get(result['thumbnail_url'])
                img_data = response.content
                image = Image.open(BytesIO(img_data)).resize((120, 80), Image.LANCZOS)
                tk_image = ctk.CTkImage(light_image=image, dark_image=image, size=(120, 80))
            except Exception as e:
                print(f"Error loading image: {e}")
                tk_image = None
            
            # Thumbnail
            if tk_image:
                thumb = ctk.CTkLabel(card, image=tk_image, text="")
                thumb.image = tk_image  # Keep reference
                thumb.grid(row=0, column=0, rowspan=2, padx=10, pady=10, sticky="nsw")
            else:
                thumb = ctk.CTkLabel(card, text="No Image", width=120, height=80)
                thumb.grid(row=0, column=0, rowspan=2, padx=10, pady=10, sticky="nsw")
            
            # Title - make it expand to fill available space
            title = ctk.CTkLabel(
                card,
                text=result['title'],
                font=ctk.CTkFont(size=16, weight="bold"),
                anchor="w",
                justify="left"
                # Remove fixed wraplength - let it adapt to available space
            )
            title.grid(row=0, column=1, sticky="nsew", padx=(0, 20), pady=(10, 2))
            
            # Additional info (uploader, duration, views)
            details = []
            if 'uploader' in result and result['uploader']:
                details.append(result['uploader'])
            if 'duration' in result and result['duration']:
                details.append(result['duration'])
                
            if details:
                details_text = " • ".join(details)
                details_label = ctk.CTkLabel(
                    card,
                    text=details_text,
                    font=ctk.CTkFont(size=14),
                    text_color="gray",
                    anchor="w",
                    justify="left"
                )
                details_label.grid(row=1, column=1, sticky="nsw", padx=(0, 20), pady=(2, 10))
            
            # Add a separator between items (except after the last one)
            if idx < len(self.results) - 1:
                separator = ctk.CTkFrame(
                    self.scrollable_frame,
                    height=1,
                    fg_color="#333333"
                )
                separator.grid(row=idx*2 + 1, column=0, sticky="ew", padx=20, pady=2)