import customtkinter as ctk
from homescreen import HomeScreen
from mainscreen import MainScreen
from player import Player

# Set appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

# Create main window
app = ctk.CTk()
app.title("HanyaMusic")
app.resizable(False, True)

# Center the window
window_width = 1920
window_height = 1080
screen_width = app.winfo_screenwidth()
screen_height = app.winfo_screenheight()
x = int((screen_width / 2) - (window_width / 2))
y = int((screen_height / 2) - (window_height / 2))
app.geometry(f"{window_width}x{window_height}+{x}+{y}")

# Create a container for the main content
content_frame = ctk.CTkFrame(app, fg_color="transparent")
content_frame.pack(fill="both", expand=True)

# Create the persistent player
player = Player(master=app)

# Screen switching logic
def show_homescreen(query=None):
    for widget in content_frame.winfo_children():
        widget.destroy()
    HomeScreen(master=content_frame, switch_to_main_callback=show_mainscreen, initial_search=query, player=player)

def show_mainscreen():
    for widget in content_frame.winfo_children():
        widget.destroy()
    MainScreen(master=content_frame, switch_to_home_callback=show_homescreen)

# Start with MainScreen
show_mainscreen()

# Run
app.mainloop()