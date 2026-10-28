import os
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask
from flask_mail import Mail

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
app.config.update(
    MAIL_SERVER=os.getenv("MAIL_SERVER", "mail.cm.co.ke"),
    MAIL_PORT=int(os.getenv("MAIL_PORT", "587")),
    MAIL_USE_TLS=os.getenv("MAIL_USE_TLS", "true").lower() == "true",
    MAIL_USE_SSL=os.getenv("MAIL_USE_SSL", "false").lower() == "true",
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_DEFAULT_SENDER=os.getenv("MAIL_DEFAULT_SENDER") or os.getenv("MAIL_USERNAME"),
    MAIL_TIMEOUT=15,
    ADMIN_EMAILS=[email.strip().lower() for email in os.getenv("ADMIN_EMAILS", "").split(",") if email.strip()],
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
)
mail = Mail(app)
from .blueprints import register_blueprints
register_blueprints(app)
