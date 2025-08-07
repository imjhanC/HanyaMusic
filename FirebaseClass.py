import firebase_admin
from firebase_admin import credentials, firestore
import hashlib
import os
import random
import string
from datetime import datetime

class FirebaseManager:
    def __init__(self):
        """Initialize Firebase Admin SDK with the provided credentials."""
        cred_path = os.path.join(os.path.dirname(__file__), 'hanyamusic-ac4ce-firebase-adminsdk-fbsvc-e2117ea06f.json')
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

    def like_song(self, username: str, song_data: dict) -> bool:
        """Add a song to user's liked songs.
        
        Args:
            username: Username of the user
            song_data: Dictionary containing song information (videoId, title, uploader, etc.)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            encrypted_username = self._encrypt_data(username)
            video_id = song_data.get('videoId')
            
            if not video_id:
                print("No video ID found in song data")
                return False
            
            # Check if user already has a liked songs document
            liked_songs_ref = self.db.collection('liked_songs')
            user_docs = liked_songs_ref.where('username', '==', encrypted_username).stream()
            
            song_url = f"https://www.youtube.com/watch?v={video_id}"
            
            # If user has existing liked songs document
            for doc in user_docs:
                user_data = doc.to_dict()
                liked_urls = user_data.get('liked_urls', [])
                
                # Check if song is already liked
                if song_url in liked_urls:
                    print(f"Song '{song_data.get('title')}' is already liked by user {username}")
                    return True
                
                # Add new song URL to the list
                liked_urls.append(song_url)
                
                # Update the document
                doc.reference.update({
                    'liked_urls': liked_urls,
                    'updated_at': firestore.SERVER_TIMESTAMP
                })
                
                print(f"Song '{song_data.get('title')}' added to liked songs for user {username}")
                return True
            
            # If no existing document, create new one
            new_user_data = {
                'username': encrypted_username,
                'liked_urls': [song_url],
                'created_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            }
            
            liked_songs_ref.add(new_user_data)
            print(f"Song '{song_data.get('title')}' added to liked songs for user {username}")
            return True
            
        except Exception as e:
            print(f"Error liking song: {str(e)}")
            return False

    def unlike_song(self, username: str, video_id: str) -> bool:
        """Remove a song from user's liked songs.
        
        Args:
            username: Username of the user
            video_id: YouTube video ID of the song to unlike
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            encrypted_username = self._encrypt_data(username)
            song_url = f"https://www.youtube.com/watch?v={video_id}"
            
            # Find user's liked songs document
            liked_songs_ref = self.db.collection('liked_songs')
            user_docs = liked_songs_ref.where('username', '==', encrypted_username).stream()
            
            for doc in user_docs:
                user_data = doc.to_dict()
                liked_urls = user_data.get('liked_urls', [])
                
                # Remove the song URL from the list
                if song_url in liked_urls:
                    liked_urls.remove(song_url)
                    
                    # If no more liked songs, delete the entire document
                    if not liked_urls:
                        doc.reference.delete()
                        print(f"Removed last liked song for user {username}, deleted user collection")
                    else:
                        # Update the document with remaining URLs
                        doc.reference.update({
                            'liked_urls': liked_urls,
                            'updated_at': firestore.SERVER_TIMESTAMP
                        })
                        print(f"Song with videoId '{video_id}' removed from liked songs for user {username}")
                    
                    return True
                
                print(f"Song with videoId '{video_id}' not found in liked songs for user {username}")
                return False
            
            print(f"No liked songs document found for user {username}")
            return False
            
        except Exception as e:
            print(f"Error unliking song: {str(e)}")
            return False

    def is_song_liked(self, username: str, video_id: str) -> bool:
        """Check if a song is liked by the user.
        
        Args:
            username: Username of the user
            video_id: YouTube video ID of the song to check
            
        Returns:
            bool: True if song is liked, False otherwise
        """
        try:
            encrypted_username = self._encrypt_data(username)
            song_url = f"https://www.youtube.com/watch?v={video_id}"
            
            # Query for user's liked songs
            liked_songs_ref = self.db.collection('liked_songs')
            user_docs = liked_songs_ref.where('username', '==', encrypted_username).stream()
            
            for doc in user_docs:
                user_data = doc.to_dict()
                liked_urls = user_data.get('liked_urls', [])
                return song_url in liked_urls
            
            return False
            
        except Exception as e:
            print(f"Error checking if song is liked: {str(e)}")
            return False

    def get_user_liked_songs(self, username: str) -> list:
        """Get all liked songs for a user.
        
        Args:
            username: Username of the user
            
        Returns:
            list: List of song URLs
        """
        try:
            encrypted_username = self._encrypt_data(username)
            
            # Query for user's liked songs
            liked_songs_ref = self.db.collection('liked_songs')
            user_docs = liked_songs_ref.where('username', '==', encrypted_username).stream()
            
            for doc in user_docs:
                user_data = doc.to_dict()
                return user_data.get('liked_urls', [])
            
            return []
            
        except Exception as e:
            print(f"Error getting liked songs: {str(e)}")
            return []

    def toggle_song_like(self, username: str, song_data: dict) -> tuple:
        """Toggle like status of a song (like if not liked, unlike if liked).
        
        Args:
            username: Username of the user
            song_data: Dictionary containing song information
            
        Returns:
            tuple: (success: bool, is_liked: bool, message: str)
        """
        video_id = song_data.get('videoId')
        if not video_id:
            return False, False, "No video ID found"
        
        try:
            # Check if song is currently liked
            is_liked = self.is_song_liked(username, video_id)
            
            if is_liked:
                # Unlike the song
                success = self.unlike_song(username, video_id)
                if success:
                    return True, False, f"Removed '{song_data.get('title')}' from liked songs"
                else:
                    return False, True, "Failed to remove song from liked songs"
            else:
                # Like the song
                success = self.like_song(username, song_data)
                if success:
                    return True, True, f"Added '{song_data.get('title')}' to liked songs"
                else:
                    return False, False, "Failed to add song to liked songs"
                    
        except Exception as e:
            print(f"Error toggling song like: {str(e)}")
            return False, False, f"Error: {str(e)}"

    def get_saved_songs_count(self, username: str) -> int:
        """Get the count of saved songs for a user.
        
        Args:
            username: Username of the user
            
        Returns:
            int: Number of saved songs (liked songs count)
        """
        try:
            encrypted_username = self._encrypt_data(username)
            
            # Query for user's liked songs
            liked_songs_ref = self.db.collection('liked_songs')
            user_docs = liked_songs_ref.where('username', '==', encrypted_username).stream()
            
            for doc in user_docs:
                user_data = doc.to_dict()
                liked_urls = user_data.get('liked_urls', [])
                return len(liked_urls)
            
            return 0
            
        except Exception as e:
            print(f"Error getting saved songs count: {str(e)}")
            return 0
        
    #  Create a new playlist for the user
    def create_playlist(self, username: str, playlist_name: str) -> bool:
        """Create a new playlist for the user, or add to existing user's playlists array."""
        try:
            encrypted_username = self._encrypt_data(username)
            playlists_ref = self.db.collection('playlists')

            # Query for existing document for this user
            user_docs = playlists_ref.where('username', '==', encrypted_username).stream()
            user_doc = None
            for doc in user_docs:
                user_doc = doc
                break

            # Use client-side timestamp for created_at
            new_playlist = {
                'name': playlist_name,
                'created_at': datetime.utcnow().isoformat(),  # Use ISO string for compatibility
                'songs': []
            }

            if user_doc:
                # Update existing document: append to playlists array
                doc_ref = user_doc.reference
                doc_ref.update({
                    'playlists': firestore.ArrayUnion([new_playlist])
                })
                print(f"Added playlist '{playlist_name}' to existing user {username}")
            else:
                # Create new document for this user
                playlist_data = {
                    'username': encrypted_username,
                    'playlists': [new_playlist]
                }
                playlists_ref.add(playlist_data)
                print(f"Created new playlist document for user {username} with playlist '{playlist_name}'")
            return True

        except Exception as e:
            print(f"Error creating playlist: {str(e)}")
            return False

    def get_user_playlists(self, username: str) -> list:
        """Get all playlists for a user as a list of playlist dicts."""
        try:
            encrypted_username = self._encrypt_data(username)
            playlists_ref = self.db.collection('playlists')
            user_docs = playlists_ref.where('username', '==', encrypted_username).stream()
            for doc in user_docs:
                user_data = doc.to_dict()
                return user_data.get('playlists', [])
            return []
        except Exception as e:
            print(f"Error getting user playlists: {str(e)}")
            return []