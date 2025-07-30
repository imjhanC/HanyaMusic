import firebase_admin
from firebase_admin import credentials, firestore
import hashlib
import os
import random
import string

class FirebaseManager:
    def __init__(self):
        """Initialize Firebase Admin SDK with the provided credentials."""
        cred_path = os.path.join(os.path.dirname(__file__), 'hanyamusic-ac4ce-firebase-adminsdk-fbsvc-402e7bb396.json')
        cred = credentials.Certificate(cred_path)
        
        try:
            firebase_admin.get_app()
        except ValueError:
            firebase_admin.initialize_app(cred)
            
        self.db = firestore.client()
    
    def _encrypt_data(self, data: str) -> str:
        """Encrypt data using SHA-256 hashing.
        
        Args:
            data: The string data to encrypt
            
        Returns:
            str: SHA-256 hashed string
        """
        return hashlib.sha256(data.encode()).hexdigest()
    
    def generate_recovery_code(self) -> str:
        """Generate a random 6-digit alphanumeric code.
        
        Returns:
            str: 6-character alphanumeric code
        """
        chars = string.ascii_letters + string.digits
        return ''.join(random.choices(chars, k=6))
    
    def is_username_available(self, username: str) -> bool:
        """Check if a username is available by checking all documents in users collection.
        
        Args:
            username: Username to check
            
        Returns:
            bool: True if username is available, False otherwise
        """
        try:
            users_ref = self.db.collection('users')
            # Get all documents and check each username
            docs = users_ref.stream()
            
            for doc in docs:
                user_data = doc.to_dict()
                stored_username = user_data.get('username', '')
                # Compare with encrypted username
                if stored_username == self._encrypt_data(username):
                    return False
            return True
            
        except Exception as e:
            print(f"Error checking username availability: {str(e)}")
            return False
    
    def register_user(self, username: str, password: str, recovery_code: str = None) -> tuple:
        """Register a new user with auto-generated document ID.
        
        Args:
            username: User's username or email
            password: User's password
            recovery_code: Optional recovery code (will generate if not provided)
            
        Returns:
            tuple: (success: bool, result: str)
        """
        # Generate recovery code if not provided
        if not recovery_code:
            recovery_code = self.generate_recovery_code()
        
        # Encrypt sensitive data
        encrypted_username = self._encrypt_data(username)
        encrypted_password = self._encrypt_data(password)
        encrypted_recovery = self._encrypt_data(recovery_code)
        
        try:
            # Store user data in Firestore with auto-generated document ID
            user_data = {
                'username': encrypted_username,
                'password': encrypted_password,
                'recovery_code': encrypted_recovery,
                'created_at': firestore.SERVER_TIMESTAMP
            }
            
            # Use add() to create document with auto-generated ID
            doc_ref = self.db.collection('users').add(user_data)
            return True, recovery_code
            
        except Exception as e:
            print(f"Error registering user: {str(e)}")
            return False, str(e)
    
    def verify_credentials(self, username: str, password: str) -> bool:
        """Verify user credentials by checking all documents.
        
        Args:
            username: Username or email
            password: Password to verify
            
        Returns:
            bool: True if credentials are valid, False otherwise
        """
        encrypted_username = self._encrypt_data(username)
        encrypted_password = self._encrypt_data(password)
        
        try:
            users_ref = self.db.collection('users')
            docs = users_ref.stream()
            
            for doc in docs:
                user_data = doc.to_dict()
                if (user_data.get('username') == encrypted_username and 
                    user_data.get('password') == encrypted_password):
                    return True
            return False
            
        except Exception as e:
            print(f"Error verifying credentials: {str(e)}")
            return False