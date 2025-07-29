import customtkinter as ctk
import re
from FirebaseClass import FirebaseManager

class RegisterPage(ctk.CTkToplevel):
    def __init__(self, switch_to_login_callback=None):
        super().__init__()
        self.firebase = FirebaseManager()
        self.switch_to_login = switch_to_login_callback
        self.title("Register - HanyaMusic")
        self.geometry("600x650")  # Slightly taller to accommodate more fields
        self.resizable(False, False)
        
        # Configure grid
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Main container
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.grid(row=0, column=0, padx=40, pady=20, sticky="nsew")
        
        # Title
        self.title_label = ctk.CTkLabel(
            self.container, 
            text="Create Account",
            font=ctk.CTkFont(size=36, weight="bold")
        )
        self.title_label.pack(pady=(0, 30))
        
        self.create_widgets()
        
        # Center the window on screen
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'+{x}+{y}')
    
    def create_widgets(self):
        # Username/Email
        self.username_label = ctk.CTkLabel(
            self.container, 
            text="Username or Email",
            anchor="w",
            width=400,
            font=ctk.CTkFont(size=14)
        )
        self.username_label.pack(pady=(0, 5), padx=(60, 0), anchor="w")
        
        self.username_var = ctk.StringVar()
        self.username_entry = ctk.CTkEntry(
            self.container,
            textvariable=self.username_var,
            placeholder_text="Enter your username or email",
            width=400,
            height=45,
            font=ctk.CTkFont(size=14)
        )
        self.username_entry.pack(pady=(0, 15))
        
        self.username_error = ctk.CTkLabel(
            self.container,
            text="",
            text_color="red",
            anchor="w",
            width=400
        )
        self.username_error.pack(pady=(0, 5), padx=(60, 0), anchor="w")
        
        # Password
        self.password_label = ctk.CTkLabel(
            self.container, 
            text="Password",
            anchor="w",
            width=400,
            font=ctk.CTkFont(size=14)
        )
        self.password_label.pack(pady=(0, 5), padx=(60, 0), anchor="w")
        
        self.password_var = ctk.StringVar()
        self.password_entry = ctk.CTkEntry(
            self.container,
            textvariable=self.password_var,
            placeholder_text="Create a password",
            width=400,
            height=45,
            show="•",
            font=ctk.CTkFont(size=14)
        )
        self.password_entry.pack(pady=(0, 10))
        
        # Password requirements
        self.req_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.req_frame.pack(pady=(0, 10))
        
        self.req_length = ctk.CTkLabel(
            self.req_frame,
            text="• At least 8 characters",
            text_color="red",
            anchor="w"
        )
        self.req_length.pack(anchor="w")
        
        self.req_upper = ctk.CTkLabel(
            self.req_frame,
            text="• At least 1 uppercase letter",
            text_color="red",
            anchor="w"
        )
        self.req_upper.pack(anchor="w")
        
        self.req_digit = ctk.CTkLabel(
            self.req_frame,
            text="• At least 1 number",
            text_color="red",
            anchor="w"
        )
        self.req_digit.pack(anchor="w")
        
        self.req_special = ctk.CTkLabel(
            self.req_frame,
            text="• At least 1 special character",
            text_color="red",
            anchor="w"
        )
        self.req_special.pack(anchor="w")
        
        # Recovery Code
        self.recovery_label = ctk.CTkLabel(
            self.container, 
            text="Recovery Code (6 digits)",
            anchor="w",
            width=400,
            font=ctk.CTkFont(size=14)
        )
        self.recovery_label.pack(pady=(10, 5), padx=(60, 0), anchor="w")
        
        self.recovery_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.recovery_frame.pack(pady=(0, 20))
        
        self.recovery_var = ctk.StringVar()
        self.recovery_entry = ctk.CTkEntry(
            self.recovery_frame,
            textvariable=self.recovery_var,
            placeholder_text="Enter 6-digit code",
            width=200,
            height=45,
            font=ctk.CTkFont(size=14)
        )
        self.recovery_entry.pack(side="left", padx=(0, 10))
        
        self.generate_btn = ctk.CTkButton(
            self.recovery_frame,
            text="Generate",
            command=self.generate_recovery_code,
            width=100,
            height=45,
            fg_color="#1DB954",
            hover_color="#1ed760"
        )
        self.generate_btn.pack(side="left")
        
        # Register Button
        self.register_btn = ctk.CTkButton(
            self.container,
            text="Register",
            command=self.register,
            width=400,
            height=45,
            fg_color="#1DB954",
            hover_color="#1ed760",
            font=ctk.CTkFont(size=17, weight="bold")
        )
        self.register_btn.pack(pady=(10, 5))
        
        # Back to Login
        self.login_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.login_frame.pack(pady=(10, 0))
        
        self.login_label = ctk.CTkLabel(
            self.login_frame,
            text="Already have an account?"
        )
        self.login_label.pack(side="left")
        
        self.login_link = ctk.CTkButton(
            self.login_frame,
            text="Log in",
            command=self.go_to_login,
            font=ctk.CTkFont(underline=True),
            fg_color="transparent",
            hover=False,
            text_color=("#1a5fb4", "#62a0ea"),
            width=0,
            height=0
        )
        self.login_link.pack(side="left", padx=5)
        
        # Error message
        self.error_label = ctk.CTkLabel(
            self.container,
            text="",
            text_color="red"
        )
        self.error_label.pack(pady=(10, 0))
        
        # Bind validation events
        self.password_var.trace('w', lambda *args: self.validate_password())
        self.username_var.trace('w', lambda *args: self.validate_username())
        self.password_entry.bind('<Return>', lambda e: self.register())
    
    def validate_password(self, *args):
        password = self.password_var.get()
        
        # Check length
        length_ok = len(password) >= 8
        self.req_length.configure(text_color="green" if length_ok else "red")
        
        # Check uppercase
        upper_ok = any(c.isupper() for c in password)
        self.req_upper.configure(text_color="green" if upper_ok else "red")
        
        # Check digit
        digit_ok = any(c.isdigit() for c in password)
        self.req_digit.configure(text_color="green" if digit_ok else "red")
        
        # Check special character
        special_ok = bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', password))
        self.req_special.configure(text_color="green" if special_ok else "red")
        
        return all([length_ok, upper_ok, digit_ok, special_ok])
    
    def validate_username(self, *args):
        username = self.username_var.get()
        if not username:
            self.username_error.configure(text="")
            return False
            
        # Simple email validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        is_email = re.match(email_pattern, username) is not None
        
        # If not email, validate as username (alphanumeric + underscore, 3-20 chars)
        if not is_email:
            if not re.match(r'^\w{3,20}$', username):
                self.username_error.configure(text="Username must be 3-20 alphanumeric characters")
                return False
        
        self.username_error.configure(text="")
        return True
    
    def generate_recovery_code(self):
        code = self.firebase.generate_recovery_code()
        self.recovery_var.set(code)
    
    def register(self):
        username = self.username_var.get().strip()
        password = self.password_var.get()
        recovery_code = self.recovery_var.get().strip()
        
        # Validate all fields
        if not all([username, password, recovery_code]):
            self.show_error("All fields are required!")
            return
            
        if not self.validate_username():
            return
            
        if not self.validate_password():
            self.show_error("Please fix password requirements!")
            return
            
        # Check username availability
        if not self.firebase.is_username_available(username):
            self.username_error.configure(text="Username/Email already exists!")
            return
        
        # Register user
        success, result = self.firebase.register_user(username, password, recovery_code)
        
        if success:
            self.show_info("Registration successful!\n\nYour recovery code is: {}\n\nPlease save this code in a safe place.".format(result))
            self.go_to_login()
        else:
            self.show_error("Registration failed: {}".format(result))
    
    def show_error(self, message):
        """Display error message"""
        self.error_label.configure(text=message, text_color="red")
        self.after(5000, lambda: self.error_label.configure(text=""))
    
    def show_info(self, message):
        """Display info message"""
        self.error_label.configure(text=message, text_color="green")
        self.after(5000, lambda: self.error_label.configure(text=""))
    
    def go_to_login(self):
        if self.switch_to_login:
            self.destroy()
            self.switch_to_login()
        else:
            # If no callback provided, just close the window
            self.destroy()

if __name__ == "__main__":
    app = ctk.CTk()
    register = RegisterPage()
    app.withdraw()
    app.mainloop()