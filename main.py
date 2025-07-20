import customtkinter as ctk
from homescreen import HomeScreen

# Set appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

# Create main window
app = ctk.CTk()
app.title("Spotify-Inspired Music Player")
app.resizable(True, True)

# Center the window
window_width = 1920
window_height = 1080
screen_width = app.winfo_screenwidth()
screen_height = app.winfo_screenheight()
x = int((screen_width / 2) - (window_width / 2))
y = int((screen_height / 2) - (window_height / 2))
app.geometry(f"{window_width}x{window_height}+{x}+{y}")

# Load Home Screen
home = HomeScreen(master=app)

# Run
app.mainloop()
