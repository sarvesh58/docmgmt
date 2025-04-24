import datetime
from pymongo import MongoClient
from bson.objectid import ObjectId
from config.config import get_config

config = get_config()


class Database:
    """Database connection class for MongoDB/DocumentDB"""
    def __init__(self):
        self.client = None
        self.db = None
        self.connect()
    
    def connect(self):
        """Connect to MongoDB"""
        try:
            self.client = MongoClient(config.MONGO_URI)
            self.db = self.client[config.MONGO_DATABASE]
            # Test the connection
            self.client.admin.command('ping')
            print("MongoDB connection established")
        except Exception as e:
            print(f"MongoDB connection error: {e}")
            # Fallback to default localhost connection if config fails
            try:
                self.client = MongoClient('mongodb://localhost:27017/')
                self.db = self.client[config.MONGO_DATABASE]
                print("Connected to local MongoDB (fallback)")
            except Exception as local_e:
                print(f"Local MongoDB connection error: {local_e}")
    
    def close(self):
        """Close the database connection"""
        if self.client:
            self.client.close()


# Initialize the database connection
db_instance = Database()

# Get database collections
users_collection = db_instance.db.users
files_collection = db_instance.db.files
file_versions_collection = db_instance.db.file_versions


class User:
    """User model for authentication and user management"""
    
    @staticmethod
    def create_user(username, email, password_hash):
        """Create a new user"""
        user = {
            "username": username,
            "email": email,
            "password_hash": password_hash,
            "created_at": datetime.datetime.now(),
            "last_login": None,
            "is_active": True,
            "is_admin": False
        }
        result = users_collection.insert_one(user)
        return result.inserted_id
    
    @staticmethod
    def get_user_by_id(user_id):
        """Get user by ID"""
        return users_collection.find_one({"_id": ObjectId(user_id)})
    
    @staticmethod
    def get_user_by_email(email):
        """Get user by email"""
        return users_collection.find_one({"email": email})
    
    @staticmethod
    def get_user_by_username(username):
        """Get user by username"""
        return users_collection.find_one({"username": username})
    
    @staticmethod
    def update_last_login(user_id):
        """Update user's last login time"""
        users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"last_login": datetime.datetime.now()}}
        )
    
    @staticmethod
    def update_user(user_id, update_data):
        """Update user information"""
        users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data}
        )


class File:
    """File model for file metadata storage"""
    
    @staticmethod
    def create_file(user_id, filename, s3_key, file_type, file_size, metadata=None):
        """Create a new file entry"""
        if metadata is None:
            metadata = {}
        
        file_doc = {
            "user_id": ObjectId(user_id),
            "filename": filename,
            "s3_key": s3_key,
            "file_type": file_type,
            "file_size": file_size,
            "metadata": metadata,
            "created_at": datetime.datetime.now(),
            "modified_at": datetime.datetime.now(),
            "is_deleted": False,
            "current_version": 1,
            "permissions": {
                "owner": str(user_id),
                "read": [str(user_id)],
                "write": [str(user_id)],
                "delete": [str(user_id)]
            }
        }
        
        result = files_collection.insert_one(file_doc)
        file_id = result.inserted_id
        
        # Create initial version record
        version_doc = {
            "file_id": file_id,
            "version_number": 1,
            "s3_key": s3_key,
            "created_at": datetime.datetime.now(),
            "created_by": ObjectId(user_id),
            "file_size": file_size,
            "comment": "Initial version"
        }
        
        file_versions_collection.insert_one(version_doc)
        return file_id
    @staticmethod
    def get_file_by_id(file_id):
        """Get file by ID"""
        try:
            # Ensure file_id is a valid ObjectId
            object_id = ObjectId(file_id) if not isinstance(file_id, ObjectId) else file_id
            return files_collection.find_one({"_id": object_id, "is_deleted": False})
        except Exception as e:
            print(f"Error converting file_id to ObjectId: {e}")
            return None
    
    @staticmethod
    def get_user_files(user_id):
        """Get all files for a user"""
        return list(files_collection.find({"user_id": ObjectId(user_id), "is_deleted": False}))
    
    @staticmethod
    def search_files(query, user_id=None):
        """Search files by filename or metadata"""
        search_conditions = {
            "$or": [
                {"filename": {"$regex": query, "$options": "i"}},
                {"metadata.title": {"$regex": query, "$options": "i"}},
                {"metadata.description": {"$regex": query, "$options": "i"}},
                {"metadata.keywords": {"$regex": query, "$options": "i"}}
            ],
            "is_deleted": False
        }
        
        # If user_id is provided, limit to files the user can read
        if user_id:
            search_conditions["$or"] = [
                {"user_id": ObjectId(user_id)},
                {"permissions.read": str(user_id)}
            ]
        
        return list(files_collection.find(search_conditions))
    
    @staticmethod
    def update_file(file_id, update_data):
        """Update file metadata"""
        update_data["modified_at"] = datetime.datetime.now()
        files_collection.update_one(
            {"_id": ObjectId(file_id)},
            {"$set": update_data}
        )
    
    @staticmethod
    def soft_delete(file_id):
        """Soft delete a file"""
        files_collection.update_one(
            {"_id": ObjectId(file_id)},
            {"$set": {"is_deleted": True, "modified_at": datetime.datetime.now()}}
        )
    
    @staticmethod
    def add_new_version(file_id, user_id, s3_key, file_size, comment=None):
        """Add a new version of a file"""
        # Get current file info
        file_info = File.get_file_by_id(file_id)
        
        if not file_info:
            return None
        
        new_version = file_info["current_version"] + 1
        
        # Create new version record
        version_doc = {
            "file_id": ObjectId(file_id),
            "version_number": new_version,
            "s3_key": s3_key,
            "created_at": datetime.datetime.now(),
            "created_by": ObjectId(user_id),
            "file_size": file_size,
            "comment": comment or f"Version {new_version}"
        }
        
        file_versions_collection.insert_one(version_doc)
        
        # Update the file's current version
        files_collection.update_one(
            {"_id": ObjectId(file_id)},
            {
                "$set": {
                    "current_version": new_version,
                    "s3_key": s3_key,
                    "file_size": file_size,
                    "modified_at": datetime.datetime.now()
                }
            }
        )
        
        return new_version
    
    @staticmethod
    def get_file_versions(file_id):
        """Get all versions of a file"""
        return list(file_versions_collection.find(
            {"file_id": ObjectId(file_id)}).sort("version_number", -1))
    
    @staticmethod
    def get_file_version(file_id, version_number):
        """Get a specific version of a file"""
        return file_versions_collection.find_one({
            "file_id": ObjectId(file_id),
            "version_number": version_number
        })


class AdminSettings:
    """Admin settings model for storing configurable application options"""
    
    @staticmethod
    def get_settings():
        """Get current admin settings, creating default if none exist"""
        settings = db_instance.db.settings.find_one({"type": "app_settings"})
        
        if not settings:
            # Create default settings
            default_settings = {
                "type": "app_settings",
                "session_timeout": 15,  # 15 minutes default
                "primary_color": "#0075BE",  # BMO blue
                "secondary_color": "#8CC6FF",  # BMO light blue
                "accent_color": "#0A8F1A",  # BMO green
                "logo_path": "img/bmo@logotyp.us.svg",
                "logo_height": 50,
                "updated_at": datetime.datetime.now(),
                "updated_by": None
            }
            print("DEBUG: Creating default settings:", default_settings)
            db_instance.db.settings.insert_one(default_settings)
            return default_settings
        
        print("DEBUG: Retrieved settings:", settings)
        return settings
    
    @staticmethod
    def update_settings(update_data, updated_by=None):
        """Update admin settings"""
        update_data["updated_at"] = datetime.datetime.now()
        update_data["updated_by"] = updated_by
        
        db_instance.db.settings.update_one(
            {"type": "app_settings"},
            {"$set": update_data},
            upsert=True
        )
        return True
    
    @staticmethod
    def get_session_timeout():
        """Get current session timeout in minutes"""
        settings = AdminSettings.get_settings()
        return settings.get("session_timeout", 15)
