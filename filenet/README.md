# FileNet-like Document Management System

A secure and scalable document management system built with Python Flask, similar to IBM FileNet. It utilizes AWS S3 for file storage and Amazon DocumentDB for database management.

## Features

- **User Authentication:** Secure registration and login system
- **File Management:** Upload, download, and manage files with versioning
- **Metadata:** Add and edit metadata for better document organization
- **Document Versions:** Comprehensive version control for all documents
- **Access Control:** Granular permissions for sharing documents
- **API Integration:** RESTful API for programmatic access to documents
- **Search Capability:** Find documents by filename, metadata, or content

## Technology Stack

- **Backend:** Python Flask
- **Database:** Amazon DocumentDB (MongoDB compatible)
- **Storage:** AWS S3 for file storage
- **Frontend:** HTML, CSS, JavaScript with Bootstrap 5
- **Authentication:** Flask-Login with bcrypt password hashing

## Prerequisites

- Python 3.8+
- AWS Account with S3 access
- Amazon DocumentDB instance (or MongoDB for development)

## Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd filenet
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv venv
   # On Windows
   venv\Scripts\activate
   # On macOS/Linux
   source venv/bin/activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Copy the example environment file and update with your settings:
   ```
   cp .env.example .env
   # Edit .env with your configuration details
   ```

5. Run the application:
   ```
   python run.py
   ```

## Environment Variables

The following environment variables should be set in the `.env` file:

```
# Application settings
SECRET_KEY=your-secret-key
FLASK_APP=run.py
FLASK_ENV=development|production|testing

# AWS S3 Configuration
AWS_S3_BUCKET=your-s3-bucket-name
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=your-aws-region

# Amazon DocumentDB Configuration
DOCDB_HOST=your-docdb-host
DOCDB_PORT=27017
DOCDB_USERNAME=your-username
DOCDB_PASSWORD=your-password
DOCDB_DATABASE=filenet_db
```

## API Usage

The application provides several API endpoints for interacting with documents:

- `GET /api/files/search?query=<search_term>` - Search for files
- `GET /api/files/<file_id>` - Retrieve a file
- `GET /api/files/<file_id>/with-metadata` - Retrieve file with metadata
- `PUT /api/files/<file_id>` - Update file and/or metadata
- `POST /api/files` - Upload a new file

API authentication is required using an Authorization header.

## Project Structure

```
filenet/
├── app/
│   ├── __init__.py         # Application factory
│   ├── api/                # API routes and resources
│   ├── auth/               # Authentication routes
│   ├── main/               # Main application routes
│   ├── models/             # Database models
│   ├── static/             # Static assets (JS, CSS)
│   ├── templates/          # HTML templates
│   └── utils/              # Utility functions
├── config/                 # Configuration settings
├── tests/                  # Unit and integration tests
├── .env.example            # Example environment variables
├── requirements.txt        # Python dependencies
└── run.py                  # Application entry point
```
