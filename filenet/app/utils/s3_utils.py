import os
import uuid
import shutil
import logging
from datetime import datetime, timedelta
import hashlib
from urllib.parse import urljoin
from config.config import get_config

# Get configuration
config = get_config()

class LocalStorage:
    """Utility class for local file storage operations"""
    def __init__(self):
        self.storage_path = config.LOCAL_STORAGE_PATH
        # Ensure storage directory exists
        os.makedirs(self.storage_path, exist_ok=True)
        
    def upload_file(self, file_data, file_path=None):
        """
        Upload a file to local storage
        
        Args:
            file_data: File data (bytes or file-like object)
            file_path: Optional path in storage (generated if not provided)
            
        Returns:
            tuple: (success, file_path or error message)
        """
        try:
            # Generate a unique key if not provided
            if file_path is None:
                file_path = f"uploads/{str(uuid.uuid4())}"
            
            # Create the full path to save the file
            full_path = os.path.join(self.storage_path, file_path)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            # Write the file to disk
            with open(full_path, 'wb') as f:
                # If file_data is a file object, read it
                if hasattr(file_data, 'read'):
                    f.write(file_data.read())
                else:
                    # If it's bytes, write directly
                    f.write(file_data)
            
            return True, file_path
        except Exception as e:
            logging.error(f"Error uploading file to local storage: {e}")
            return False, str(e)
    
    def download_file(self, file_path):
        """
        Download a file from local storage
        
        Args:
            file_path: File path within the storage directory
            
        Returns:
            tuple: (success, file_data or error message)
        """
        try:
            full_path = os.path.join(self.storage_path, file_path)
            
            if not os.path.exists(full_path):
                return False, f"File not found: {file_path}"
            
            with open(full_path, 'rb') as f:
                file_data = f.read()
            
            return True, file_data
        except Exception as e:
            logging.error(f"Error downloading file from local storage: {e}")
            return False, str(e)
    
    def delete_file(self, file_path):
        """
        Delete a file from local storage
        
        Args:
            file_path: File path within the storage directory
            
        Returns:
            tuple: (success, message)
        """
        try:
            full_path = os.path.join(self.storage_path, file_path)
            
            if not os.path.exists(full_path):
                return False, f"File not found: {file_path}"
            
            os.remove(full_path)
            
            return True, "File deleted successfully"        
        except Exception as e:
            logging.error(f"Error deleting file from local storage: {e}")
            return False, str(e)
    
    def generate_presigned_url(self, file_path, expiration=3600):
        """
        Generate a URL for a file (simulates presigned URL but for local storage)
        
        Args:
            file_path: File path within the storage directory
            expiration: Expiration time in seconds (not used for local files, but kept for API compatibility)
            
        Returns:
            tuple: (success, url or error message)
        """
        try:
            full_path = os.path.join(self.storage_path, file_path)
            
            if not os.path.exists(full_path):
                return False, f"File not found: {file_path}"
            
            # For local files, we'll use a simple file:// URL or a relative path
            # This depends on how your application will access the files
            # For demonstration, we'll create a token-based URL approach
            
            # Generate a simple token based on the file path and current time
            # This is a very simple implementation and not secure for production
            timestamp = datetime.now().timestamp()
            expiry = timestamp + expiration
            token = hashlib.md5(f"{file_path}:{expiry}".encode()).hexdigest()
            
            # In a real application, you would store this token and expiry in a database
            # For this example, we'll just return a URL with the token
            url = f"/files/{file_path}?token={token}&expires={int(expiry)}"
            
            return True, url
        except Exception as e:
            logging.error(f"Error generating URL for local file: {e}")
            return False, str(e)
    
    def create_lifecycle_policy(self, prefix, days_to_archive=90, days_to_delete=365):
        """
        Simulate S3 lifecycle policy for local storage
        
        Args:
            prefix: Path prefix for files
            days_to_archive: Days after which to archive files (stub implementation)
            days_to_delete: Days after which to delete files
            
        Returns:
            tuple: (success, message)
        """
        # For local storage, we'll implement a simple cleanup function
        # that could be called periodically by a scheduler
        try:
            # This would typically be scheduled to run periodically
            # For now, we'll just log a message for demonstration
            logging.info(f"Local storage lifecycle policy registered for prefix '{prefix}'")
            logging.info(f"Files will be deleted after {days_to_delete} days")
            
            # In a real implementation, you could scan the directory and delete old files
            # For example:
            '''
            delete_before = datetime.now() - timedelta(days=days_to_delete)
            for root, dirs, files in os.walk(os.path.join(self.storage_path, prefix)):
                for file in files:
                    file_path = os.path.join(root, file)
                    file_mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    if file_mod_time < delete_before:
                        os.remove(file_path)
            '''
            
            return True, "Lifecycle policy simulation registered successfully"
        except Exception as e:
            logging.error(f"Error creating local storage lifecycle policy: {e}")
            return False, str(e)
