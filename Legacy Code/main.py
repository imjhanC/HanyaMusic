import customtkinter as ctk
from homescreen import HomeScreen
from mainscreen import MainScreen

# Set appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

# Create main window
app = ctk.CTk()
app.title("HanyaMusic")
app.resizable(False, False)

# Center the window
window_width = 1920
window_height = 1080
screen_width = app.winfo_screenwidth()
screen_height = app.winfo_screenheight()
x = int((screen_width / 2) - (window_width / 2))
y = int((screen_height / 2) - (window_height / 2))
app.geometry(f"{window_width}x{window_height}+{x}+{y}")

# Screen switching logic
def show_homescreen(query=None):
    for widget in app.winfo_children():
        widget.destroy()
    HomeScreen(master=app, switch_to_main_callback=show_mainscreen, initial_search=query)

def show_mainscreen():
    for widget in app.winfo_children():
        widget.destroy()
    MainScreen(master=app, switch_to_home_callback=show_homescreen)

# Start with MainScreen
show_mainscreen()

# Run
app.mainloop()
