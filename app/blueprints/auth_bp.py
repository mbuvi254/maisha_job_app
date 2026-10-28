"""Shared passwordless authentication for candidates, employers, and administrators."""
import hashlib
import hmac
import re
import secrets
from urllib.parse import urlsplit

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for

from app.repository.auth_repository import AuthRepository
from app.services.candidate_service import get_candidate_by_email
from app.services.employer_service import get_employer_by_email, set_employer_verified_status, get_all_employers
from app.services.verification_service import generate_otp, send_verification_email

admin_bp = Blueprint('admin_bp', __name__, url_prefix='/admin')
repo = AuthRepository()
ENDPOINTS = {
    'candidate': ('candidate_bp.login_candidate', 'candidate_bp.verify_candidate', 'candidate_bp.resend_candidate_otp', 'candidate_bp.candidate_profile'),
    'employer': ('employer_bp.login_employer', 'employer_bp.verify_employer', 'employer_bp.resend_employer_otp', 'employer_bp.employer_dashboard'),
    'admin': ('admin_bp.login_admin', 'admin_bp.verify_admin', 'admin_bp.resend_admin_otp', 'admin_bp.dashboard'),
}


def csrf_token():
    if 'auth_csrf' not in session:
        session['auth_csrf'] = secrets.token_urlsafe(32)
    return session['auth_csrf']


def check_csrf():
    if not hmac.compare_digest(session.get('auth_csrf', ''), request.form.get('csrf_token', '')) or not session.get('auth_csrf'):
        abort(400, description='Your form expired. Reload the page and try again.')


def safe_next(value):
    if not value or '\\' in value or any(ord(c) < 32 for c in value):
        return None
    parsed = urlsplit(value)
    return value if value.startswith('/') and not value.startswith('//') and not parsed.netloc and not parsed.scheme else None


def account(role, email):
    if role == 'admin':
        return {'id': email, 'email': email} if email in current_app.config['ADMIN_EMAILS'] else None
    user = get_candidate_by_email(email) if role == 'candidate' else get_employer_by_email(email)
    return None if isinstance(user, tuple) else user


def digest(challenge_id, role, email, code):
    return hmac.new(current_app.secret_key.encode(), f'{challenge_id}:{role}:{email}:{code}'.encode(), hashlib.sha256).hexdigest()


def page(role, verifying=False, **kwargs):
    pending = session.get(f'{role}_challenge', {})
    return render_template('auth/login.html', role=role, verifying=verifying, pending=pending,
                           endpoints=ENDPOINTS[role], roles=ENDPOINTS, csrf_token=csrf_token(), **kwargs)


def send_code(role, email, account_id):
    challenge_id = secrets.token_hex(32)
    code = generate_otp()
    if not repo.issue(challenge_id, role, email, digest(challenge_id, role, email, code)):
        return 'Please wait 60 seconds before requesting another code.'
    if not send_verification_email(email, code):
        repo.discard(challenge_id)
        return 'We could not send your code. Please try again or contact support.'
    session[f'{role}_challenge'] = {'id': challenge_id, 'email': email, 'account_id': account_id}
    return None


def begin_registration(role, email, account_id):
    # Registration is not an authenticated session, even if delivery fails.
    session.pop(f'{role}_id', None)
    session.pop(f'{role}_email', None)
    try:
        error = send_code(role, email, account_id)
    except Exception:
        current_app.logger.exception('Registration OTP unavailable')
        error = 'Sign-in is temporarily unavailable. Please try again shortly.'
    if error:
        return page(role, error=error), 503
    flash('Your account is ready. Check your email for a sign-in code.', 'success')
    return redirect(url_for(ENDPOINTS[role][1]))


def login(role):
    if request.method == 'GET':
        legacy_pending = 'candidate_pending_verification' if role == 'candidate' else 'pending_verification' if role == 'employer' else None
        if legacy_pending and session.pop(legacy_pending, None):
            session.pop(f'{role}_id', None)
            session.pop(f'{role}_email', None)
        target = safe_next(request.args.get('next'))
        if target:
            session[f'{role}_next_url'] = target
        if request.args.get('restart'):
            session.pop(f'{role}_challenge', None)
        if session.get(f'{role}_id'):
            return redirect(url_for(ENDPOINTS[role][3]))
        if session.get(f'{role}_challenge'):
            return redirect(url_for(ENDPOINTS[role][1]))
        return page(role)
    check_csrf()
    email = request.form.get('email', '').strip().lower()
    if len(email) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        return page(role, error='Enter a valid email address.'), 400
    try:
        user = account(role, email)
        if not user:
            return page(role, error='No account is available for this email and role. Check your email or create an account.'), 400
        error = send_code(role, email, user['id'])
        if error:
            return page(role, error=error), 429 if '60 seconds' in error else 503
    except Exception:
        current_app.logger.exception('OTP sign-in unavailable')
        return page(role, error='Sign-in is temporarily unavailable. Please try again shortly.'), 503
    return redirect(url_for(ENDPOINTS[role][1]))


def verify(role):
    pending = session.get(f'{role}_challenge')
    if not pending:
        return redirect(url_for(ENDPOINTS[role][0]))
    if request.method == 'GET':
        return page(role, verifying=True)
    check_csrf()
    code = request.form.get('otp', '').strip()
    try:
        # Count every submitted value, including malformed codes, toward the limit.
        if not repo.consume(pending['id'], role, pending['email'], digest(pending['id'], role, pending['email'], code)):
            return page(role, verifying=True, error='Invalid or expired code. Codes expire after 10 minutes or 5 attempts. Request a new code to try again.'), 400
        user = account(role, pending['email'])
        if not user or str(user['id']) != str(pending['account_id']):
            session.pop(f'{role}_challenge', None)
            return page(role, error='This account is no longer available.'), 403
        if role == 'employer':
            # Only set verified status if not already verified
            if not user.get('verified', False):
                result = set_employer_verified_status(user['id'], True)
                if isinstance(result, tuple):
                    raise RuntimeError('Could not activate employer')
    except Exception:
        current_app.logger.exception('OTP verification unavailable')
        return page(role, verifying=True, error='Verification is temporarily unavailable. Please request a new code and try again.'), 503
    target = safe_next(session.get(f'{role}_next_url')) or url_for(ENDPOINTS[role][3])
    # Rotate authentication state; one active role per browser prevents role confusion.
    session.clear()
    session.permanent = True
    session[f'{role}_id'] = user['id']
    session[f'{role}_email'] = pending['email']
    return redirect(target)


def resend(role):
    check_csrf()
    pending = session.get(f'{role}_challenge')
    if not pending:
        return redirect(url_for(ENDPOINTS[role][0]))
    try:
        error = send_code(role, pending['email'], pending['account_id'])
    except Exception:
        current_app.logger.exception('OTP resend unavailable')
        error = 'We could not send a code. Please try again shortly.'
    return page(role, verifying=True, error=error, success=None if error else 'A new code is on its way. Use the most recent email.'), (429 if error and '60 seconds' in error else 503 if error else 200)


@admin_bp.route('/login', methods=['GET', 'POST'])
def login_admin():
    return login('admin')


@admin_bp.route('/verify', methods=['GET', 'POST'])
def verify_admin():
    return verify('admin')


@admin_bp.post('/resend-otp')
def resend_admin_otp():
    return resend('admin')


@admin_bp.get('/')
@admin_bp.get('/dashboard')
def dashboard():
    if session.get('admin_email') not in current_app.config['ADMIN_EMAILS'] or not session.get('admin_id'):
        return redirect(url_for('admin_bp.login_admin'))
    from app.services.job_service import get_all_jobs
    try:
        from app.services.admin_service import get_platform_activity
        from datetime import datetime
        employers = get_all_employers()
        jobs = get_all_jobs(hide_expired=False)
        active_jobs = sum(1 for job in jobs if not job.get("deadline") or job["deadline"] > datetime.now())
        return render_template('admin/dashboard.html', employers=employers, jobs=jobs,
                               active_jobs=active_jobs, activity=get_platform_activity())
    except Exception:
        current_app.logger.exception('Admin dashboard unavailable')
        return render_template('admin/dashboard.html', employers=[], jobs=[], active_jobs=0, activity={'totals': {}, 'statuses': [], 'recent': []}, error='The database is temporarily unavailable.'), 503


@admin_bp.post('/logout')
def logout():
    check_csrf()
    session.clear()
    return redirect(url_for('admin_bp.login_admin'))


@admin_bp.app_context_processor
def auth_context():
    return {'auth_csrf_token': csrf_token}


@admin_bp.after_app_request
def prevent_auth_caching(response):
    if request.path.startswith(('/admin', '/employers', '/candidates')) or any(session.get(f'{role}_id') for role in ENDPOINTS):
        response.headers['Cache-Control'] = 'no-store'
    return response
