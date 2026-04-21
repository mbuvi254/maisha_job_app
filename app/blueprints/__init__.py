from .employer_bp import employer_bp
from .jobs_bp import jobs_bp

def register_blueprints(app):
    app.register_blueprint(employer_bp)
    app.register_blueprint(jobs_bp)