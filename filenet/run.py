import os
from app import create_app
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get configuration from environment
config_name = os.getenv('FLASK_ENV', 'development')

# Create the Flask application
app = create_app(config_name)

if __name__ == '__main__':
    # Run the application
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
