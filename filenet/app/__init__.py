from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_session import Session as FlaskSession
import os
import datetime
from werkzeug.utils import secure_filename

from config.config import get_config
from app.api.routes import api_bp


def create_app(config_name='default'):
    """Create and configure the Flask application."""
    app = Flask(__name__)
      # Load configuration
    app_config = get_config(config_name)
    app.config.from_object(app_config)
    
    # Configure URL handling - make Flask redirect URLs with a trailing slash
    # to their non-trailing slash counterpart
    app.url_map.strict_slashes = False
    
    # Ensure the upload folder exists
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    
    # Initialize Flask-Session
    FlaskSession(app)
    
    # Register blueprints
    from app.api.routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
      # Import and register auth blueprint
    from app.auth.routes import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    # Import and register main blueprint
    from app.main.routes import main_bp
    app.register_blueprint(main_bp)
    
    # Import and register admin blueprint
    from app.admin.routes import admin_bp
    app.register_blueprint(admin_bp)
    
    # Load dynamic settings from database
    from app.models.models import AdminSettings
    settings = AdminSettings.get_settings()
    
    # Apply dynamic session timeout if set in database
    app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(minutes=settings.get('session_timeout', 15))
      # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def server_error(error):
        return render_template('errors/500.html'), 500
    
    @app.before_request
    def refresh_session_timeout():
        """Reset the session timeout on user activity if the user is logged in"""
        if 'user_id' in session:
            session.modified = True
    
    @app.context_processor
    def utility_processor():
        """Add utility functions to template context"""
        def format_datetime(date):
            if isinstance(date, datetime.datetime):
                return date.strftime('%Y-%m-%d %H:%M:%S')
            return date
        
        return dict(format_datetime=format_datetime)
    
    return app
