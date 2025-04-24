from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file, send_from_directory
from werkzeug.utils import secure_filename
import os
import io
import json
from bson.objectid import ObjectId
import datetime

from app.models.models import File, users_collection
from app.utils.s3_utils import LocalStorage
from app.utils.auth_utils import login_required, get_current_user

# Create blueprint
main_bp = Blueprint('main', __name__)

# Initialize local storage
s3_storage = LocalStorage()


@main_bp.route('/')
def index():
    """Landing page"""
    user = get_current_user()
    return render_template('index.html', user=user)


@main_bp.route('/dashboard')
@login_required
def dashboard():
    """User dashboard showing their files"""
    user = get_current_user()
    files = File.get_user_files(user['_id'])
    return render_template('dashboard.html', user=user, files=files)


@main_bp.route('/files/upload', methods=['GET', 'POST'])
@login_required
def upload_file():
    """File upload page"""
    user = get_current_user()
    
    if request.method == 'POST':
        # Check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
        
        file = request.files['file']
        
        # If user does not select file, browser submits empty part
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
        
        # Check if the file type is allowed
        if file and '.' in file.filename:
            file_ext = file.filename.rsplit('.', 1)[1].lower()
            if file_ext not in current_app.config['ALLOWED_EXTENSIONS']:
                flash(f'File type .{file_ext} is not allowed', 'danger')
                return redirect(request.url)
        
        # Proceed with file upload if it's valid
        if file:
            filename = secure_filename(file.filename)
            
            # Get metadata from form
            title = request.form.get('title', '')
            description = request.form.get('description', '')
            keywords = request.form.get('keywords', '')
            
            # Create metadata dictionary
            metadata = {
                'title': title,
                'description': description,
                'keywords': keywords.split(',') if keywords else []
            }
            
            # Upload to S3
            user_id = str(user['_id'])
            file_path = f"users/{user_id}/{filename}"
            success, s3_key = s3_storage.upload_file(file, file_path)
            
            if not success:
                flash(f'Error uploading file: {s3_key}', 'danger')
                return redirect(request.url)
            
            # Get file extension
            file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
            
            # Create file record in database
            file_size = os.fstat(file.fileno()).st_size
            file_id = File.create_file(
                user['_id'],
                filename,
                s3_key,
                file_ext,
                file_size,
                metadata
            )
            
            flash('File uploaded successfully!', 'success')
            return redirect(url_for('main.view_file', file_id=file_id))
    
    return render_template('upload.html', user=user)


@main_bp.route('/files/<file_id>')
@login_required
def view_file(file_id):
    """View file details page"""
    user = get_current_user()
    user_id = str(user['_id'])
    
    try:
        # Get file info - ensure proper ObjectId conversion
        file_info = File.get_file_by_id(file_id)
        
        if not file_info:
            flash('File not found', 'danger')
            return redirect(url_for('main.dashboard'))
    except Exception as e:
        print(f"Error retrieving file: {e}")
        flash('Error retrieving file', 'danger')
        return redirect(url_for('main.dashboard'))
    
    # Check permissions
    if (str(file_info['user_id']) != user_id and 
        user_id not in file_info['permissions']['read']):
        flash('You do not have permission to view this file', 'danger')
        return redirect(url_for('main.dashboard'))
    
    # Get file versions
    versions = File.get_file_versions(file_id)
    
    # Generate a URL for previewing
    preview_url = url_for('main.serve_preview', file_id=file_id)
    
    return render_template('view_file.html', 
                          user=user, 
                          file=file_info, 
                          versions=versions,
                          preview_url=preview_url)


@main_bp.route('/files/<file_id>/download')
@login_required
def download_file(file_id):
    """Download a file"""
    user = get_current_user()
    user_id = str(user['_id'])
    version = request.args.get('version')
    
    # Get file info
    file_info = File.get_file_by_id(file_id)
    
    if not file_info:
        flash('File not found', 'danger')
        return redirect(url_for('main.dashboard'))
    
    # Check permissions
    if (str(file_info['user_id']) != user_id and 
        user_id not in file_info['permissions']['read']):
        flash('You do not have permission to download this file', 'danger')
        return redirect(url_for('main.dashboard'))
    
    # Get specific version if requested
    s3_key = file_info['s3_key']
    if version:
        version_info = File.get_file_version(file_id, int(version))
        if not version_info:
            flash('Version not found', 'danger')
            return redirect(url_for('main.view_file', file_id=file_id))
        s3_key = version_info['s3_key']
    
    # Download file from S3
    success, file_data = s3_storage.download_file(s3_key)
    
    if not success:
        flash(f'Error downloading file: {file_data}', 'danger')
        return redirect(url_for('main.view_file', file_id=file_id))
    
    # Create in-memory file
    file_io = io.BytesIO(file_data)
    
    # Return file
    return send_file(
        file_io,
        download_name=file_info['filename'],
        as_attachment=True
    )


@main_bp.route('/files/preview/<file_id>')
@login_required
def serve_preview(file_id):
    """Serve file content for previewing, checking permissions."""
    user = get_current_user()
    user_id = str(user['_id'])

    try:
        file_info = File.get_file_by_id(file_id)
        if not file_info:
            return "File not found", 404
    except Exception as e:
        print(f"Error retrieving file for preview: {e}")
        return "Error retrieving file", 500

    # Check permissions
    if (str(file_info['user_id']) != user_id and
            user_id not in file_info['permissions']['read']):
        return "Forbidden", 403

    # Construct the full path using the storage utility's path
    try:
        # s3_key stores the relative path within the storage directory
        file_relative_path = file_info['s3_key']
        directory = os.path.join(current_app.root_path, '..', s3_storage.storage_path, os.path.dirname(file_relative_path))
        filename = os.path.basename(file_relative_path)
        
        # Use send_from_directory for security
        return send_from_directory(directory, filename)
    except FileNotFoundError:
        return "File not found on server", 404
    except Exception as e:
        print(f"Error serving file preview: {e}")
        return "Error serving file", 500


@main_bp.route('/files/<file_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_file(file_id):
    """Edit file metadata page"""
    user = get_current_user()
    user_id = str(user['_id'])
    
    # Get file info
    file_info = File.get_file_by_id(file_id)
    
    if not file_info:
        flash('File not found', 'danger')
        return redirect(url_for('main.dashboard'))
    
    # Check permissions
    if (str(file_info['user_id']) != user_id and 
        user_id not in file_info['permissions']['write']):
        flash('You do not have permission to edit this file', 'danger')
        return redirect(url_for('main.view_file', file_id=file_id))
    
    if request.method == 'POST':
        # Get metadata from form
        title = request.form.get('title', '')
        description = request.form.get('description', '')
        keywords = request.form.get('keywords', '')
        
        # Create metadata dictionary
        metadata = {
            'title': title,
            'description': description,
            'keywords': keywords.split(',') if keywords else []
        }
        
        # Update file in database
        update_data = {
            'metadata': metadata
        }
        File.update_file(file_id, update_data)
        
        # Handle file update if a new file was uploaded
        if 'file' in request.files and request.files['file'].filename:
            file = request.files['file']
            filename = secure_filename(file.filename)
            
            # Upload to S3
            file_path = f"users/{user_id}/{filename}"
            success, s3_key = s3_storage.upload_file(file, file_path)
            
            if not success:
                flash(f'Error uploading file: {s3_key}', 'danger')
                return redirect(request.url)
            
            # Add new version
            comment = request.form.get('comment', '')
            file_size = os.fstat(file.fileno()).st_size
            new_version = File.add_new_version(
                file_id, 
                user_id, 
                s3_key, 
                file_size,
                comment
            )
            
            if not new_version:
                flash('Failed to create new version', 'danger')
                return redirect(request.url)
        
        flash('File updated successfully!', 'success')
        return redirect(url_for('main.view_file', file_id=file_id))
    
    return render_template('edit_file.html', user=user, file=file_info)


@main_bp.route('/files/search')
@login_required
def search_files():
    """Search files page"""
    user = get_current_user()
    query = request.args.get('query', '')
    
    if not query:
        return render_template('search.html', user=user, files=[], query='')
    
    files = File.search_files(query, str(user['_id']))
    
    return render_template('search.html', user=user, files=files, query=query)


@main_bp.route('/files/<file_id>/share', methods=['GET', 'POST'])
@login_required
def share_file(file_id):
    """Share file page to manage permissions"""
    user = get_current_user()
    user_id = str(user['_id'])
    
    # Get file info
    file_info = File.get_file_by_id(file_id)
    
    if not file_info:
        flash('File not found', 'danger')
        return redirect(url_for('main.dashboard'))
    
    # Check if user is the owner
    if str(file_info['user_id']) != user_id:
        flash('Only the owner can modify sharing settings', 'danger')
        return redirect(url_for('main.view_file', file_id=file_id))
    
    if request.method == 'POST':
        # Get shared users from form
        read_users = request.form.getlist('read_users')
        write_users = request.form.getlist('write_users')
        delete_users = request.form.getlist('delete_users')
        
        # Update permissions
        permissions = {
            'owner': user_id,
            'read': read_users,
            'write': write_users,
            'delete': delete_users
        }
        
        # Always ensure owner has all permissions
        if user_id not in permissions['read']:
            permissions['read'].append(user_id)
        if user_id not in permissions['write']:
            permissions['write'].append(user_id)
        if user_id not in permissions['delete']:
            permissions['delete'].append(user_id)
        
        # Update file in database
        update_data = {
            'permissions': permissions
        }
        File.update_file(file_id, update_data)
        
        flash('Sharing settings updated successfully!', 'success')
        return redirect(url_for('main.view_file', file_id=file_id))
      # Get all users for sharing options
    # In a real application, this should be paginated or filtered
    all_users = list(users_collection.find({}, {'username': 1, 'email': 1}))
    
    return render_template('share_file.html', 
                          user=user, 
                          file=file_info, 
                          all_users=all_users)


@main_bp.route('/files/<file_id>/delete', methods=['POST'])
@login_required
def delete_file(file_id):
    """Delete a file (soft delete)"""
    user = get_current_user()
    user_id = str(user['_id'])
    
    # Get file info
    file_info = File.get_file_by_id(file_id)
    
    if not file_info:
        flash('File not found', 'danger')
        return redirect(url_for('main.dashboard'))
    
    # Check permissions
    if (str(file_info['user_id']) != user_id and 
        user_id not in file_info['permissions']['delete']):
        flash('You do not have permission to delete this file', 'danger')
        return redirect(url_for('main.view_file', file_id=file_id))
    
    # Soft delete the file
    File.soft_delete(file_id)
    
    flash('File deleted successfully', 'success')
    return redirect(url_for('main.dashboard'))


@main_bp.route('/files/<file_id>/restore/<int:version>', methods=['POST'])
@login_required
def restore_version(file_id, version):
    """Restore a previous version of a file"""
    user = get_current_user()
    user_id = str(user['_id'])
    
    # Get file info
    file_info = File.get_file_by_id(file_id)
    
    if not file_info:
        flash('File not found', 'danger')
        return redirect(url_for('main.dashboard'))
    
    # Check permissions
    if (str(file_info['user_id']) != user_id and 
        user_id not in file_info['permissions']['write']):
        flash('You do not have permission to modify this file', 'danger')
        return redirect(url_for('main.view_file', file_id=file_id))
    
    # Get the version to restore
    version_info = File.get_file_version(file_id, version)
    if not version_info:
        flash('Version not found', 'danger')
        return redirect(url_for('main.view_file', file_id=file_id))
    
    # Update the file to the previous version
    update_data = {
        's3_key': version_info['s3_key'],
        'current_version': version,
        'modified_at': datetime.datetime.utcnow()
    }
    
    success = File.update_file(file_id, update_data)
    
    if success:
        flash(f'Successfully restored to version {version}', 'success')
    else:
        flash('Error restoring version', 'danger')
        return redirect(url_for('main.view_file', file_id=file_id))
