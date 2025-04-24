# Admin routes for FileNet application
from flask import render_template, request, redirect, url_for, flash, current_app, jsonify
import os
import datetime
from werkzeug.utils import secure_filename
from config.config import get_config

from app.models.models import User, AdminSettings, users_collection
from app.utils.auth_utils import login_required, get_current_user
from app.admin import admin_bp

# Custom decorator to require admin privileges
def admin_required(view_func):
    """Decorator to require admin role for access to views"""
    @login_required
    def wrapped_view(*args, **kwargs):
        user = get_current_user()
        if not user or not user.get('is_admin', False):
            flash('You need administrator privileges to access this page.', 'danger')
            return redirect(url_for('main.index'))
        return view_func(*args, **kwargs)
    wrapped_view.__name__ = view_func.__name__
    return wrapped_view

@admin_bp.route('/')
@admin_required
def index():
    """Admin dashboard page"""
    try:
        user = get_current_user()
        settings = AdminSettings.get_settings()
        
        # Debug info
        if not user:
            print("DEBUG: No user found for admin dashboard")
        else:
            print(f"DEBUG: User {user.get('username')} accessing admin dashboard")
        
        if not settings:
            print("DEBUG: No settings found for admin dashboard")
            # Provide default settings if none are found
            settings = {
                "session_timeout": 15,
                "primary_color": "#0075BE",
                "secondary_color": "#8CC6FF",
                "accent_color": "#0A8F1A",
                "logo_path": "img/bmo@logotyp.us.svg",
                "logo_height": 50
            }
        
        return render_template('admin/dashboard.html', user=user, settings=settings)
    except Exception as e:
        print(f"ERROR in admin dashboard: {e}")
        flash(f"An error occurred: {str(e)}", "danger")
        return redirect(url_for('main.index'))

@admin_bp.route('/settings', methods=['GET', 'POST'])
@admin_required
def settings():
    """Admin settings page"""
    user = get_current_user()
    
    # Debug info
    print(f"DEBUG: User accessing admin settings: {user.get('username') if user else 'None'}")
    
    if request.method == 'POST':
        # Update settings based on form data
        session_timeout = int(request.form.get('session_timeout', 15))
        primary_color = request.form.get('primary_color', '#0075BE')
        secondary_color = request.form.get('secondary_color', '#8CC6FF')
        accent_color = request.form.get('accent_color', '#0A8F1A')
        logo_height = int(request.form.get('logo_height', 50))
        
        # Handle logo upload if provided
        logo_path = None
        if 'logo_file' in request.files and request.files['logo_file'].filename:
            logo_file = request.files['logo_file']
            # Ensure the upload folder exists
            logo_dir = os.path.join(current_app.root_path, 'static', 'img', 'custom')
            os.makedirs(logo_dir, exist_ok=True)
            
            # Secure the filename and save the file
            filename = secure_filename(logo_file.filename)
            logo_path = os.path.join('img', 'custom', filename)
            full_path = os.path.join(current_app.root_path, 'static', logo_path)
            logo_file.save(full_path)
        
        # Build update data
        update_data = {
            "session_timeout": session_timeout,
            "primary_color": primary_color,
            "secondary_color": secondary_color,
            "accent_color": accent_color,
            "logo_height": logo_height
        }
        
        # Only update logo path if a new file was uploaded
        if logo_path:
            update_data["logo_path"] = logo_path
        
        # Update settings in database
        AdminSettings.update_settings(update_data, user['_id'])
        
        # Update session lifetime in the Flask app config
        current_app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(minutes=session_timeout)
        
        flash('Settings updated successfully', 'success')
        return redirect(url_for('admin.settings'))
    
    # GET request - show settings form
    settings = AdminSettings.get_settings()
    return render_template('admin/settings.html', user=user, settings=settings)

@admin_bp.route('/users')
@admin_required
def users():
    """Admin users management page"""
    user = get_current_user()
    all_users = list(users_collection.find())
    return render_template('admin/users.html', user=user, users=all_users)

@admin_bp.route('/users/<user_id>/toggle-admin', methods=['POST'])
@admin_required
def toggle_admin(user_id):
    """Toggle admin status for a user"""
    try:
        target_user = User.get_user_by_id(user_id)
        if not target_user:
            flash('User not found', 'danger')
            return redirect(url_for('admin.users'))
        
        # Toggle is_admin status
        new_status = not target_user.get('is_admin', False)
        User.update_user(user_id, {'is_admin': new_status})
        
        status_text = "granted to" if new_status else "revoked from"
        flash(f"Admin privileges {status_text} {target_user['username']}", 'success')
    except Exception as e:
        flash(f"Error updating user: {e}", 'danger')
    
    return redirect(url_for('admin.users'))

@admin_bp.route('/preview-theme', methods=['POST'])
@admin_required
def preview_theme():
    """API endpoint to generate CSS for theme preview"""
    primary_color = request.form.get('primary_color', '#0075BE')
    secondary_color = request.form.get('secondary_color', '#8CC6FF') 
    accent_color = request.form.get('accent_color', '#0A8F1A')
    
    # Generate CSS for the theme preview
    css = f"""
    :root {{
        --bmo-blue: {primary_color};
        --bmo-light-blue: {secondary_color};
        --bmo-green: {accent_color};
    }}
    """
    
    return jsonify({'css': css})
