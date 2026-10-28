from .employer_bp import employer_bp
from .candidate_bp import candidate_bp
from .jobs_bp import jobs_bp

from .auth_bp import admin_bp

def register_blueprints(app):
    app.register_blueprint(admin_bp)
    app.register_blueprint(employer_bp)
    app.register_blueprint(candidate_bp)
    app.register_blueprint(jobs_bp)
