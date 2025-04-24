from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from werkzeug.urls import url_parse

from app.models.models import User
from app.utils.auth_utils import hash_password, verify_password, login_user, logout_user, get_current_user

# Create blueprint
auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page"""
    # If user is already logged in, redirect to home
    if get_current_user():
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        # Get form data
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        # Validate form data
        error = None
        
        if not username:
            error = 'Username is required.'
        elif not email:
            error = 'Email is required.'
        elif not password:
            error = 'Password is required.'
        elif password != confirm_password:
            error = 'Passwords do not match.'
        elif User.get_user_by_username(username):
            error = f"User {username} is already registered."
        elif User.get_user_by_email(email):
            error = f"Email {email} is already registered."
        
        if error is None:
            # Create new user
            hashed_password = hash_password(password)
            user_id = User.create_user(username, email, hashed_password)
            
            # Log in the new user
            login_user(user_id)
            
            flash('Registration successful! Welcome to FileNet.', 'success')
            return redirect(url_for('main.index'))
        
        flash(error, 'danger')
    
    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login page"""
    # If user is already logged in, redirect to home
    if get_current_user():
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        # Get form data
        username = request.form['username']
        password = request.form['password']
        
        # Validate form data
        error = None
        user = None
        
        if not username:
            error = 'Username is required.'
        elif not password:
            error = 'Password is required.'
        else:
            # Try to find user by username or email
            user = User.get_user_by_username(username)
            if not user:
                user = User.get_user_by_email(username)
            
            if not user:
                error = 'Invalid username or password.'
            elif not verify_password(user['password_hash'], password):
                error = 'Invalid username or password.'
        
        if error is None:
            # Log in the user
            login_user(user['_id'])
            
            # Handle "next" parameter (redirect after login)
            next_page = request.args.get('next')
            if not next_page or url_parse(next_page).netloc != '':
                next_page = url_for('main.index')
            
            flash('Login successful!', 'success')
            return redirect(next_page)
        
        flash(error, 'danger')
    
    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    """User logout"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/profile')
def profile():
    """User profile page"""
    user = get_current_user()
    if not user:
        flash('You need to log in to view your profile.', 'danger')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/profile.html', user=user)


@auth_bp.route('/profile/edit', methods=['GET', 'POST'])
def edit_profile():
    """Edit user profile page"""
    user = get_current_user()
    if not user:
        flash('You need to log in to edit your profile.', 'danger')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        # Get form data
        email = request.form['email']
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Validate form data
        error = None
        update_data = {}
        
        # Update email if changed
        if email != user['email']:
            if User.get_user_by_email(email):
                error = f"Email {email} is already in use."
            else:
                update_data['email'] = email
        
        # Update password if provided
        if new_password:
            if not current_password:
                error = 'Current password is required to set a new password.'
            elif not verify_password(user['password_hash'], current_password):
                error = 'Current password is incorrect.'
            elif new_password != confirm_password:
                error = 'New passwords do not match.'
            else:
                update_data['password_hash'] = hash_password(new_password)
        
        if error is None:
            if update_data:
                User.update_user(user['_id'], update_data)
                flash('Profile updated successfully.', 'success')
            return redirect(url_for('auth.profile'))
        
        flash(error, 'danger')
    
    return render_template('auth/edit_profile.html', user=user)
