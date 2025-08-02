import os
import json
import time
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
import base64
import hashlib
import tempfile
import shutil

class SessionManager:
    def __init__(self):
        # Try multiple locations for session storage
        self.session_locations = [
            os.path.join(os.path.expanduser("~"), ".hanyamusic_session"),
            os.path.join(tempfile.gettempdir(), "hanyamusic_session"),
            os.path.join(os.getcwd(), ".hanyamusic_session")
        ]
        
        self.key_locations = [
            os.path.join(os.path.expanduser("~"), ".hanyamusic_key"),
            os.path.join(tempfile.gettempdir(), "hanyamusic_key"),
            os.path.join(os.getcwd(), ".hanyamusic_key")
        ]
        
        self.session_file = None
        self.key_file = None
        self.max_session_days = 30
        
        # Find working locations
        self._find_working_locations()
        
    def _find_working_locations(self):
        """Find writable locations for session and key files"""
        # Test session file location
        for location in self.session_locations:
            try:
                # Test if we can write to this location
                test_file = location + "_test"
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
                self.session_file = location
                break
            except (PermissionError, OSError):
                continue
        
        # Test key file location
        for location in self.key_locations:
            try:
                # Test if we can write to this location
                test_file = location + "_test"
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
                self.key_file = location
                break
            except (PermissionError, OSError):
                continue
        
        # Fallback to temp directory if nothing works
        if not self.session_file:
            self.session_file = os.path.join(tempfile.gettempdir(), f"hanyamusic_session_{os.getpid()}")
        if not self.key_file:
            self.key_file = os.path.join(tempfile.gettempdir(), f"hanyamusic_key_{os.getpid()}")
        
    def _get_or_create_key(self):
        """Get or create encryption key"""
        try:
            if os.path.exists(self.key_file):
                with open(self.key_file, 'rb') as f:
                    return f.read()
            else:
                key = Fernet.generate_key()
                # Try to save the key
                try:
                    with open(self.key_file, 'wb') as f:
                        f.write(key)
                    # Try to hide the key file on Windows
                    if os.name == 'nt':
                        try:
                            os.system(f'attrib +h "{self.key_file}"')
                        except:
                            pass  # Ignore if we can't hide the file
                except (PermissionError, OSError) as e:
                    print(f"Warning: Could not save encryption key to {self.key_file}: {e}")
                    # Use a temporary key for this session only
                    pass
                return key
        except Exception as e:
            print(f"Error handling encryption key: {e}")
            return Fernet.generate_key()
    
    def _encrypt_data(self, data):
        """Encrypt session data"""
        try:
            key = self._get_or_create_key()
            fernet = Fernet(key)
            json_data = json.dumps(data)
            encrypted_data = fernet.encrypt(json_data.encode())
            return encrypted_data
        except Exception as e:
            print(f"Error encrypting data: {e}")
            return None
    
    def _decrypt_data(self, encrypted_data):
        """Decrypt session data"""
        try:
            key = self._get_or_create_key()
            fernet = Fernet(key)
            decrypted_data = fernet.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
        except Exception as e:
            print(f"Error decrypting data: {e}")
            return None
    
    def save_session(self, username, remember_me=False):
        """Save user session with optional remember me functionality"""
        if not remember_me:
            # If remember me is not checked, clear any existing session
            self.clear_session()
            return True
        
        if not self.session_file:
            print("Error: No writable location found for session file")
            return False
        
        try:
            session_data = {
                'username': username,
                'login_time': time.time(),
                'expires_at': time.time() + (self.max_session_days * 24 * 60 * 60),  # 30 days from now
                'remember_me': True
            }
            
            encrypted_data = self._encrypt_data(session_data)
            if encrypted_data:
                # Use atomic write to prevent corruption
                temp_file = self.session_file + ".tmp"
                try:
                    with open(temp_file, 'wb') as f:
                        f.write(encrypted_data)
                    
                    # Atomic move
                    if os.path.exists(self.session_file):
                        os.remove(self.session_file)
                    shutil.move(temp_file, self.session_file)
                    
                    # Try to hide the session file on Windows
                    if os.name == 'nt':
                        try:
                            os.system(f'attrib +h "{self.session_file}"')
                        except:
                            pass  # Ignore if we can't hide the file
                    
                    print(f"Session saved successfully to: {self.session_file}")
                    return True
                except Exception as e:
                    print(f"Error writing session file: {e}")
                    # Clean up temp file if it exists
                    if os.path.exists(temp_file):
                        try:
                            os.remove(temp_file)
                        except:
                            pass
                    return False
        except Exception as e:
            print(f"Error saving session: {e}")
            return False
    
    def get_saved_session(self):
        """Get saved session if valid"""
        try:
            if not os.path.exists(self.session_file):
                return None
            
            with open(self.session_file, 'rb') as f:
                encrypted_data = f.read()
            
            session_data = self._decrypt_data(encrypted_data)
            if not session_data:
                return None
            
            # Check if session has expired
            current_time = time.time()
            if current_time > session_data.get('expires_at', 0):
                self.clear_session()
                return None
            
            # Check if remember_me was enabled
            if not session_data.get('remember_me', False):
                return None
            
            return {
                'username': session_data.get('username'),
                'login_time': session_data.get('login_time'),
                'expires_at': session_data.get('expires_at')
            }
        
        except Exception as e:
            print(f"Error reading session: {e}")
            # If there's any error reading the session, clear it
            self.clear_session()
            return None
    
    def clear_session(self):
        """Clear saved session (logout)"""
        try:
            if os.path.exists(self.session_file):
                os.remove(self.session_file)
            return True
        except Exception as e:
            print(f"Error clearing session: {e}")
            return False
    
    def is_session_valid(self):
        """Check if current session is valid"""
        session = self.get_saved_session()
        return session is not None
    
    def get_session_info(self):
        """Get session information for display"""
        session = self.get_saved_session()
        if session:
            login_time = datetime.fromtimestamp(session['login_time'])
            expires_at = datetime.fromtimestamp(session['expires_at'])
            return {
                'username': session['username'],
                'login_time': login_time.strftime('%Y-%m-%d %H:%M:%S'),
                'expires_at': expires_at.strftime('%Y-%m-%d %H:%M:%S'),
                'days_remaining': (expires_at - datetime.now()).days
            }
        return None
    
    def extend_session(self):
        """Extend current session by another 30 days"""
        session = self.get_saved_session()
        if session:
            return self.save_session(session['username'], remember_me=True)
        return False