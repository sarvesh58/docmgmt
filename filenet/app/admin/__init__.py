# Admin module initialization
from flask import Blueprint

# Create blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')
