import customtkinter as ctk
from PIL import Image, ImageTk
import os

class LoginWindow(ctk.CTkToplevel):
    def __init__(self, parent, on_login_success=None):
        super().__init__(parent)
        self.title("Login to HanyaMusic")
        self.geometry("600x500")
        self.resizable(False, False)
        self.grab_set()  # Make window modal
        
        # Center the window on screen
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'+{x}+{y}')
        
        # Store callback
        self.on_login_success = on_login_success
        
        # Configure grid
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Main container
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.grid(row=0, column=0, padx=40, pady=40, sticky="nsew")
        
        # Title
        self.title_label = ctk.CTkLabel(
            self.container, 
            text="Welcome Back!",
            font=ctk.CTkFont(size=36, weight="bold")
        )
        self.title_label.pack(pady=(0, 30))
        
        # Username
        self.username_label = ctk.CTkLabel(
            self.container, 
            text="Username",
            anchor="w",
            width=400,
            font=ctk.CTkFont(size=14)
        )
        self.username_label.pack(pady=(0, 5), padx=(60, 0), anchor="w")
        
        self.username_entry = ctk.CTkEntry(
            self.container,
            placeholder_text="Enter your username",
            width=400,
            height=45,
            font=ctk.CTkFont(size=14)
        )
        self.username_entry.pack(pady=(0, 15))
        
        # Password
        self.password_label = ctk.CTkLabel(
            self.container, 
            text="Password",
            anchor="w",
            width=400,
            font=ctk.CTkFont(size=14)
        )
        self.password_label.pack(pady=(0, 5), padx=(60, 0), anchor="w")
        
        self.password_entry = ctk.CTkEntry(
            self.container,
            placeholder_text="Enter your password",
            width=400,
            height=45,
            show="•",
            font=ctk.CTkFont(size=14)
        )
        self.password_entry.pack(pady=(0, 20))
        
        # Login button
        self.login_button = ctk.CTkButton(
            self.container,
            text="Log In",
            command=self.attempt_login,
            width=400,
            height=45,
            fg_color="#1DB954",
            hover_color="#1ed760",
            font=ctk.CTkFont(size=17, weight="bold")
        )
        self.login_button.pack(pady=(10, 5))
        
        # Sign up link
        self.signup_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.signup_frame.pack(pady=(10, 0))
        
        self.signup_label = ctk.CTkLabel(
            self.signup_frame,
            text="Don't have an account?"
        )
        self.signup_label.pack(side="left")
        
        self.signup_link = ctk.CTkButton(
            self.signup_frame,
            text="Sign up",
            command=self.on_signup_clicked,
            font=ctk.CTkFont(underline=True),
            fg_color="transparent",
            hover=False,
            text_color=("#1a5fb4", "#62a0ea"),
            width=0,
            height=0
        )
        self.signup_link.pack(side="left", padx=5)
        
        # Error message
        self.error_label = ctk.CTkLabel(
            self.container,
            text="",
            text_color="red"
        )
        self.error_label.pack(pady=(10, 0))
        
        # Bind Enter key to login
        self.password_entry.bind('<Return>', lambda e: self.attempt_login())
        
    def attempt_login(self):
        """Handle login attempt"""
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        
        # Basic validation
        if not username or not password:
            self.show_error("Please enter both username and password")
            return
            
        # Here you would typically validate credentials with your backend
        # For now, we'll simulate a successful login
        if self.validate_credentials(username, password):
            self.on_login_success(username)
            self.destroy()
        else:
            self.show_error("Invalid username or password")
    
    def validate_credentials(self, username, password):
        """Validate user credentials (placeholder - implement your own validation)"""
        # TODO: Replace with actual authentication logic
        return True  # For demo purposes
    
    def show_error(self, message):
        """Display error message"""
        self.error_label.configure(text=message)
        self.error_label.pack()
        self.after(5000, lambda: self.error_label.configure(text=""))
    
    def on_signup_clicked(self):
        """Handle signup link click"""
        # TODO: Implement signup functionality
        print("Sign up clicked")
        # You can open a signup window here
        self.show_error("Sign up functionality coming soon!")