import bcrypt
import functools
from flask import session, redirect, url_for, flash, request
from app.models.models import User


def hash_password(password):
    """Hash a password using bcrypt"""
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt)


def verify_password(stored_hash, provided_password):
    """Verify a password against a stored hash"""
    password_bytes = provided_password.encode('utf-8')
    stored_bytes = stored_hash.encode('utf-8') if isinstance(stored_hash, str) else stored_hash
    return bcrypt.checkpw(password_bytes, stored_bytes)


def login_user(user_id):
    """Log in a user by setting user ID in session"""
    session.clear()
    session['user_id'] = str(user_id)
    User.update_last_login(user_id)


def logout_user():
    """Log out a user by clearing session"""
    session.clear()


def is_logged_in():
    """Check if a user is logged in"""
    return 'user_id' in session


def get_current_user():
    """Get the currently logged in user"""
    if 'user_id' in session:
        return User.get_user_by_id(session['user_id'])
    return None


def login_required(view):
    """Decorator to require login for views"""
    @functools.wraps(view)
    def wrapped_view(*args, **kwargs):
        if not is_logged_in():
            flash('You need to login first.', 'danger')
            return redirect(url_for('auth.login', next=request.url))
        return view(*args, **kwargs)
    return wrapped_view


def admin_required(view):
    """Decorator to require admin privileges for views"""
    @functools.wraps(view)
    def wrapped_view(*args, **kwargs):
        user = get_current_user()
        if not user or not user.get('is_admin', False):
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('index'))
        return view(*args, **kwargs)
    return wrapped_view
