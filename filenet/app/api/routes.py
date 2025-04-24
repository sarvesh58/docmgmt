from flask import Blueprint, request, jsonify, send_file, current_app
from flask_restful import Api, Resource
from werkzeug.utils import secure_filename
from bson.objectid import ObjectId
from io import BytesIO
import os
import datetime

from app.models.models import File, User
from app.utils.s3_utils import LocalStorage
from app.utils.auth_utils import login_required, get_current_user

# Create blueprint
api_bp = Blueprint('api', __name__)
api = Api(api_bp)

# Initialize local storage
s3_storage = LocalStorage()

def allowed_file(filename):
    """Check if a file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


def validate_token(token):
    """Validate API token (placeholder for actual token validation)"""
    # In a real application, you would validate against stored tokens
    # For now, this is a simple placeholder that accepts any non-empty token
    return bool(token and token.strip())


def get_user_from_token(token):
    """Get user from API token (placeholder for actual implementation)"""
    # In a real application, you would look up the user associated with the token
    # For now, return the first admin user (for development only)
    return User.get_user_by_username('admin')


def api_auth_required(func):
    """Decorator to require API authentication"""
    def wrapper(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token or not validate_token(token):
            return {'error': 'Authentication required'}, 401
        
        # Add user to request for use in the handler
        request.user = get_user_from_token(token)
        if not request.user:
            return {'error': 'Invalid authentication token'}, 401
        
        return func(*args, **kwargs)
    
    return wrapper


class FileSearchAPI(Resource):
    """API resource for searching files"""
    
    @api_auth_required
    def get(self):
        """Search files and return metadata only"""
        query = request.args.get('query', '')
        user_id = str(request.user['_id'])
        
        try:
            files = File.search_files(query, user_id)
            
            # Return only metadata, not file contents
            results = []
            for file in files:
                # Convert ObjectId to string for JSON serialization
                file['_id'] = str(file['_id'])
                file['user_id'] = str(file['user_id'])
                
                # Remove S3 key for security
                file.pop('s3_key', None)
                
                # Format dates for JSON
                if 'created_at' in file:
                    file['created_at'] = file['created_at'].isoformat()
                if 'modified_at' in file:
                    file['modified_at'] = file['modified_at'].isoformat()
                
                results.append(file)
            
            return {'status': 'success', 'results': results}, 200
            
        except Exception as e:
            current_app.logger.error(f"Error in file search: {str(e)}")
            return {'status': 'error', 'message': str(e)}, 500


class FileRetrieveAPI(Resource):
    """API resource for retrieving files"""
    
    @api_auth_required
    def get(self, file_id):
        """Retrieve a file without metadata"""
        version = request.args.get('version')
        user_id = str(request.user['_id'])
        
        try:
            # Get file info
            file_info = File.get_file_by_id(file_id)
            
            if not file_info:
                return {'status': 'error', 'message': 'File not found'}, 404
            
            # Check permissions
            if (str(file_info['user_id']) != user_id and 
                user_id not in file_info['permissions']['read']):
                return {'status': 'error', 'message': 'Permission denied'}, 403
            
            # Get specific version if requested
            s3_key = file_info['s3_key']
            if version:
                version_info = File.get_file_version(file_id, int(version))
                if not version_info:
                    return {'status': 'error', 'message': 'Version not found'}, 404
                s3_key = version_info['s3_key']
            
            # Download file from S3
            success, file_data = s3_storage.download_file(s3_key)
            
            if not success:
                return {'status': 'error', 'message': file_data}, 500
            
            # Create in-memory file
            file_io = BytesIO(file_data)
            
            # Return file
            return send_file(
                file_io,
                download_name=file_info['filename'],
                as_attachment=True
            )
            
        except Exception as e:
            current_app.logger.error(f"Error retrieving file: {str(e)}")
            return {'status': 'error', 'message': str(e)}, 500


class FileWithMetadataAPI(Resource):
    """API resource for retrieving files with metadata"""
    
    @api_auth_required
    def get(self, file_id):
        """Retrieve a file with its metadata"""
        version = request.args.get('version')
        user_id = str(request.user['_id'])
        
        try:
            # Get file info
            file_info = File.get_file_by_id(file_id)
            
            if not file_info:
                return {'status': 'error', 'message': 'File not found'}, 404
            
            # Check permissions
            if (str(file_info['user_id']) != user_id and 
                user_id not in file_info['permissions']['read']):
                return {'status': 'error', 'message': 'Permission denied'}, 403
            
            # Get specific version if requested
            s3_key = file_info['s3_key']
            if version:
                version_info = File.get_file_version(file_id, int(version))
                if not version_info:
                    return {'status': 'error', 'message': 'Version not found'}, 404
                s3_key = version_info['s3_key']
            
            # Download file from S3
            success, file_data = s3_storage.download_file(s3_key)
            
            if not success:
                return {'status': 'error', 'message': file_data}, 500
            
            # Prepare metadata
            metadata = {
                'file_id': str(file_info['_id']),
                'filename': file_info['filename'],
                'file_type': file_info['file_type'],
                'file_size': file_info['file_size'],
                'created_at': file_info['created_at'].isoformat(),
                'modified_at': file_info['modified_at'].isoformat(),
                'current_version': file_info['current_version'],
                'metadata': file_info.get('metadata', {})
            }
            
            # Create in-memory file
            file_io = BytesIO(file_data)
            
            # Generate a presigned URL instead of returning the file directly
            success, url = s3_storage.generate_presigned_url(s3_key)
            
            if not success:
                return {'status': 'error', 'message': url}, 500
            
            # Return metadata with download URL
            return {
                'status': 'success', 
                'metadata': metadata,
                'download_url': url
            }, 200
            
        except Exception as e:
            current_app.logger.error(f"Error retrieving file with metadata: {str(e)}")
            return {'status': 'error', 'message': str(e)}, 500


class FileModifyAPI(Resource):
    """API resource for modifying files and metadata"""
    
    @api_auth_required
    def put(self, file_id):
        """Update file and/or metadata"""
        user_id = str(request.user['_id'])
        
        try:
            # Get file info
            file_info = File.get_file_by_id(file_id)
            
            if not file_info:
                return {'status': 'error', 'message': 'File not found'}, 404
            
            # Check permissions
            if (str(file_info['user_id']) != user_id and 
                user_id not in file_info['permissions']['write']):
                return {'status': 'error', 'message': 'Permission denied'}, 403
            
            # Update metadata if provided
            metadata_update = request.json.get('metadata')
            if metadata_update:
                update_data = {'metadata': metadata_update}
                File.update_file(file_id, update_data)
            
            # Update file if provided
            if 'file' in request.files:
                file = request.files['file']
                
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    
                    # Upload to S3
                    file_path = f"users/{user_id}/{filename}"
                    success, s3_key = s3_storage.upload_file(file, file_path)
                    
                    if not success:
                        return {'status': 'error', 'message': s3_key}, 500
                    
                    # Add new version
                    comment = request.form.get('comment', '')
                    new_version = File.add_new_version(
                        file_id, 
                        user_id, 
                        s3_key, 
                        file.content_length,
                        comment
                    )
                    
                    if not new_version:
                        return {'status': 'error', 'message': 'Failed to create new version'}, 500
            
            # Get updated file info
            file_info = File.get_file_by_id(file_id)
            file_info['_id'] = str(file_info['_id'])
            file_info['user_id'] = str(file_info['user_id'])
            
            # Format dates for JSON
            if 'created_at' in file_info:
                file_info['created_at'] = file_info['created_at'].isoformat()
            if 'modified_at' in file_info:
                file_info['modified_at'] = file_info['modified_at'].isoformat()
            
            # Remove S3 key for security
            file_info.pop('s3_key', None)
            
            return {
                'status': 'success', 
                'message': 'File updated successfully',
                'file': file_info
            }, 200
            
        except Exception as e:
            current_app.logger.error(f"Error updating file: {str(e)}")
            return {'status': 'error', 'message': str(e)}, 500
    
    @api_auth_required
    def post(self):
        """Upload a new file"""
        user_id = str(request.user['_id'])
        
        try:
            # Check if file is included in request
            if 'file' not in request.files:
                return {'status': 'error', 'message': 'No file provided'}, 400
            
            file = request.files['file']
            
            if not file or not file.filename:
                return {'status': 'error', 'message': 'Invalid file'}, 400
            
            if not allowed_file(file.filename):
                return {'status': 'error', 'message': 'File type not allowed'}, 400
            
            # Secure the filename
            filename = secure_filename(file.filename)
            
            # Get metadata
            metadata = request.form.get('metadata', '{}')
            if isinstance(metadata, str):
                import json
                try:
                    metadata = json.loads(metadata)
                except:
                    metadata = {}
            
            # Upload to S3
            file_path = f"users/{user_id}/{filename}"
            success, s3_key = s3_storage.upload_file(file, file_path)
            
            if not success:
                return {'status': 'error', 'message': s3_key}, 500
            
            # Get file extension
            file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
            
            # Create file record
            file_id = File.create_file(
                user_id,
                filename,
                s3_key,
                file_ext,
                file.content_length,
                metadata
            )
            
            return {
                'status': 'success',
                'message': 'File uploaded successfully',
                'file_id': str(file_id)
            }, 201
            
        except Exception as e:
            current_app.logger.error(f"Error uploading file: {str(e)}")
            return {'status': 'error', 'message': str(e)}, 500


# Register API resources
api.add_resource(FileSearchAPI, '/files/search')
api.add_resource(FileRetrieveAPI, '/files/<file_id>')
api.add_resource(FileWithMetadataAPI, '/files/<file_id>/with-metadata')
api.add_resource(FileModifyAPI, '/files', '/files/<file_id>')
