import os
import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Base configuration class"""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'default-dev-key-change-in-production')
      # Local Storage Configuration (replacing AWS S3)
    LOCAL_STORAGE_PATH = os.environ.get('LOCAL_STORAGE_PATH', os.path.join('C:', os.sep, 'Users', 'sarve', 'VScode workspace', 'filenet', 's3_file'))
    
    # Keeping AWS S3 config for backwards compatibility
    AWS_S3_BUCKET = os.environ.get('AWS_S3_BUCKET', 'filenet-storage')
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', '')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', '')
    AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
      # MongoDB Configuration
    MONGO_HOST = os.environ.get('MONGO_HOST', 'localhost')
    MONGO_PORT = int(os.environ.get('MONGO_PORT', 27017))
    MONGO_USERNAME = os.environ.get('MONGO_USERNAME', '')
    MONGO_PASSWORD = os.environ.get('MONGO_PASSWORD', '')
    MONGO_DATABASE = os.environ.get('MONGO_DATABASE', 'filenet_db')
    
    # MongoDB connection URI (local MongoDB by default)
    MONGO_URI = os.environ.get('MONGO_URI', f'mongodb://localhost:27017/{MONGO_DATABASE}')
    
    # File upload settings
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'temp_uploads')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 50 * 1024 * 1024))  # 50MB default
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'jpg', 'jpeg', 'png', 'gif'}
      # Session configuration
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = True  # Setting this to True enables session lifetime control
    SESSION_USE_SIGNER = True
    PERMANENT_SESSION_LIFETIME = datetime.timedelta(minutes=15)  # Set session timeout to 15 minutes


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False


class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = False
    TESTING = True
    # Use a separate test database
    MONGO_DATABASE = os.environ.get('TEST_MONGO_DATABASE', 'filenet_test_db')
    # Override MongoDB URI for testing
    MONGO_URI = os.environ.get('TEST_MONGO_URI', f'mongodb://localhost:27017/{MONGO_DATABASE}')
    # Use a test S3 bucket
    AWS_S3_BUCKET = os.environ.get('TEST_AWS_S3_BUCKET', 'filenet-test-storage')


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    # Ensure SECRET_KEY is set for production
    SECRET_KEY = os.environ.get('SECRET_KEY')
    
    # Production should have stricter security measures
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True


# Create a configuration dictionary
config_dict = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

def get_config(config_name='default'):
    """Retrieve configuration by name"""
    return config_dict.get(config_name, config_dict['default'])
