from datetime import datetime
from urllib.parse import urlparse

from flask import send_from_directory, abort, Blueprint, flash, redirect, render_template, request, session, url_for

from app.services.application_service import get_applications_by_candidate_id, get_application_by_id
from app.services.interview_service import get_interview_by_application_id, get_interview_responses, evaluate_saved_response, interview_summary
from app.services.candidate_service import get_candidate_by_email, get_candidate_by_id, get_or_create_candidate, update_candidate_cv
from app.services.saved_job_service import get_saved_jobs_by_candidate_id
from app.services.job_service import get_job_by_id, get_all_jobs
from app.services.candidate_resume_service import save_profile_cv, cv_directory, match_open_jobs
from app.services.verification_service import (
    delete_verification_otp,
    generate_otp,
    get_otp,
    save_verification_otp,
    send_verification_email,
)


candidate_bp = Blueprint('candidate_bp', __name__, url_prefix='/candidates')


def _safe_next_url(value):
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc:
        return None
    if not value.startswith('/'):
        return None
    return value


def _candidate_is_logged_in():
    return bool(session.get('candidate_id')) and not session.get('candidate_pending_verification')


def _candidate_is_pending_verification():
    return bool(session.get('candidate_pending_verification'))


def _candidate_from_session():
    candidate_id = session.get('candidate_id')
    if not candidate_id:
        return None
    candidate = get_candidate_by_id(candidate_id)
    if not candidate:
        session.pop('candidate_id', None)
        session.pop('candidate_email', None)
    return candidate


def _candidate_redirect_target():
    return _safe_next_url(session.pop('candidate_next_url', None)) or url_for('jobs_bp.index')


def _candidate_profile_context():
    candidate = _candidate_from_session()
    applications = []
    saved_jobs = []
    if candidate:
        applications = get_applications_by_candidate_id(candidate['id'])
        saved_jobs = get_saved_jobs_by_candidate_id(candidate['id'])
    return candidate, applications, saved_jobs


@candidate_bp.route('/register', methods=['GET', 'POST'])
def register_candidate():
    next_url = _safe_next_url(request.args.get('next')) or _safe_next_url(session.get('candidate_next_url'))
    if next_url:
        session['candidate_next_url'] = next_url

    if _candidate_is_pending_verification():
        return redirect(url_for('candidate_bp.verify_candidate'))

    if _candidate_is_logged_in():
        return redirect(_candidate_redirect_target())

    if request.method == 'GET':
        return render_template('candidate/candidate_register.html', next_url=session.get('candidate_next_url'))

    from app.blueprints.auth_bp import check_csrf
    check_csrf()

    data = {
        'first_name': request.form.get('first_name', '').strip(),
        'last_name': request.form.get('last_name', '').strip(),
        'email': request.form.get('email', '').strip().lower(),
        'phone': request.form.get('phone', '').strip(),
    }

    import re
    if len(data['email']) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', data['email']):
        return render_template('candidate/candidate_register.html', error="Enter a valid email address."), 400

    if not data['first_name'] or not data['email']:
        return render_template('candidate/candidate_register.html', error="First name and email are required", next_url=session.get('candidate_next_url'))

    existing = get_candidate_by_email(data['email'])
    if existing:
        return render_template('candidate/candidate_register.html', error="Candidate already exists. Please log in instead.", next_url=session.get('candidate_next_url'))

    candidate = get_or_create_candidate(data)
    if isinstance(candidate, tuple):
        return render_template('candidate/candidate_register.html', error=candidate[0].get('error', 'Registration failed'), next_url=session.get('candidate_next_url'))

    from app.blueprints.auth_bp import begin_registration
    return begin_registration("candidate", data['email'], candidate['id'])


@candidate_bp.route('/login', methods=['GET', 'POST'])
def login_candidate():
    from app.blueprints.auth_bp import login
    return login("candidate")


@candidate_bp.route('/verify', methods=['GET', 'POST'])
def verify_candidate():
    from app.blueprints.auth_bp import verify
    return verify("candidate")


@candidate_bp.route('/resend-otp', methods=['POST'])
def resend_candidate_otp():
    from app.blueprints.auth_bp import resend
    return resend("candidate")


@candidate_bp.route('/logout', methods=['GET'])
def candidate_logout():
    session.pop('active_interview', None)
    session.pop('candidate_challenge', None)
    session.pop('candidate_id', None)
    session.pop('candidate_email', None)
    session.pop('candidate_verify_email', None)
    session.pop('candidate_register_data', None)
    session.pop('candidate_login_attempt', None)
    session.pop('candidate_auth_flow', None)
    session.pop('candidate_pending_verification', None)
    session.pop('candidate_next_url', None)

    flash("You have been logged out", "success")
    return redirect(url_for('jobs_bp.index'))


@candidate_bp.route('/profile', methods=['GET'])
def candidate_profile():
    if _candidate_is_pending_verification():
        return redirect(url_for('candidate_bp.verify_candidate'))

    if not _candidate_is_logged_in():
        return redirect(url_for('candidate_bp.login_candidate', next=url_for('candidate_bp.candidate_profile')))

    candidate, applications, saved_jobs = _candidate_profile_context()
    if not candidate:
        return redirect(url_for('candidate_bp.login_candidate', next=url_for('candidate_bp.candidate_profile')))

    # Enrich applications with job details
    applications_with_jobs = []
    for application in applications:
        job = get_job_by_id(application.get('job_id'))
        if not isinstance(job, tuple):
            applications_with_jobs.append({
                **application,
                'job': job,
                'interview': get_interview_by_application_id(application['id'])
            })
        else:
            applications_with_jobs.append(application)

    pending_interviews = [application for application in applications_with_jobs
                          if application.get("job", {}).get("ai_enabled") and
                          (not application.get("interview") or application["interview"].get("status") != "completed")]
    matches = match_open_jobs(candidate["cv_text"], get_all_jobs(hide_expired=True),
                              [application["job_id"] for application in applications]) if candidate.get("cv_text") else []
    return render_template(
        'candidate/candidate_profile.html',
        candidate=candidate,
        applications=applications_with_jobs,
        saved_jobs=saved_jobs,
        pending_interviews=pending_interviews,
        matched_jobs=matches,
    )



@candidate_bp.get('/applications/<string:application_id>')
def application_detail(application_id):
    candidate = _candidate_from_session() if _candidate_is_logged_in() else None
    if not candidate:
        return redirect(url_for('candidate_bp.login_candidate', next=request.path))
    application = get_application_by_id(application_id)
    if not application or str(application.get('user_id')) != str(candidate['id']):
        abort(404)
    job = get_job_by_id(application['job_id'])
    if isinstance(job, tuple):
        job = None
    interview = get_interview_by_application_id(application_id)
    responses = get_interview_responses(interview['id']) if interview else []
    return render_template('candidate/application_detail.html', candidate=candidate,
                           application=application, job=job, interview=interview, responses=responses, summary=interview_summary(responses))



@candidate_bp.post('/profile/cv')
def upload_cv():
    if not _candidate_is_logged_in():
        return redirect(url_for('candidate_bp.login_candidate', next=url_for('candidate_bp.candidate_profile')))
    from app.blueprints.auth_bp import check_csrf
    check_csrf()
    candidate = _candidate_from_session()
    if not candidate:
        abort(401)
    upload = request.files.get('cv')
    if not upload or not upload.filename:
        flash('Choose a resume / CV to upload.', 'warning')
        return redirect(url_for('candidate_bp.candidate_profile'))
    try:
        data = save_profile_cv(upload)
    except ValueError as exc:
        flash(str(exc), 'danger')
        return redirect(url_for('candidate_bp.candidate_profile'))
    try:
        update_candidate_cv(candidate['id'], data)
    except Exception:
        (cv_directory() / data['cv_filename']).unlink(missing_ok=True)
        raise
    from app.services.site_activity_service import record_upload
    record_upload()
    # Do not remove previous CVs: submitted applications may reference earlier versions.
    flash('CV uploaded. Your job matches have been refreshed.', 'success')
    return redirect(url_for('candidate_bp.candidate_profile') + '#job-matches')


@candidate_bp.get('/profile/cv')
def download_cv():
    candidate = _candidate_from_session() if _candidate_is_logged_in() else None
    if not candidate:
        abort(401)
    if not candidate.get('cv_filename'):
        abort(404)
    response = send_from_directory(cv_directory(), candidate['cv_filename'], as_attachment=True,
                                   download_name=candidate.get('cv_name') or 'resume.pdf')
    response.headers['Cache-Control'] = 'private, no-store'
    return response



@candidate_bp.post('/applications/<string:application_id>/responses/<string:response_id>/retry-feedback')
def retry_feedback(application_id, response_id):
    if not _candidate_is_logged_in():
        abort(401)
    from app.blueprints.auth_bp import check_csrf
    check_csrf()
    application = get_application_by_id(application_id)
    if not application or str(application.get("user_id")) != str(session["candidate_id"]):
        abort(404)
    interview = get_interview_by_application_id(application_id)
    if not interview:
        abort(404)
    response = next((row for row in get_interview_responses(interview["id"]) if row["id"] == response_id), None)
    if not response:
        abort(404)
    if response.get("evaluation_status") == "pending":
        job = get_job_by_id(application["job_id"])
        if isinstance(job, tuple):
            abort(404)
        try:
            evaluate_saved_response(job, interview["id"], response)
            flash("Feedback is ready.", "success")
        except Exception:
            flash("Your answer remains saved. AI feedback is still unavailable; please check again later.", "info")
    return redirect(url_for("candidate_bp.application_detail", application_id=application_id))


@candidate_bp.route('/matches', methods=['GET', 'POST'])
def resume_matches():
    from app.blueprints.auth_bp import check_csrf
    from app.services.site_activity_service import guest_resume, save_guest
    candidate = _candidate_from_session() if _candidate_is_logged_in() else None
    data = candidate if candidate else guest_resume(session.get('guest_resume_token'))
    if request.method == 'POST':
        check_csrf()
        import time
        if time.time() - session.get('last_resume_upload', 0) < 60:
            flash('Please wait a minute before uploading another resume.', 'warning')
            return redirect(url_for('candidate_bp.resume_matches'))
        upload = request.files.get('cv')
        try:
            if not upload or not upload.filename:
                raise ValueError('Choose a PDF or DOCX resume.')
            saved = save_profile_cv(upload)
            try:
                if candidate:
                    update_candidate_cv(candidate['id'], saved)

                else:
                    session['guest_resume_token'] = save_guest(saved)
                    session.permanent = True
            except Exception:
                (cv_directory() / saved['cv_filename']).unlink(missing_ok=True)
                raise
            session['last_resume_upload'] = time.time()
            if candidate:
                from app.services.site_activity_service import record_upload
                record_upload()
            return redirect(url_for('candidate_bp.resume_matches'))
        except ValueError as exc:
            flash(str(exc), 'danger')
    matches = match_open_jobs(data.get('cv_text', ''), get_all_jobs(hide_expired=True), limit=None) if data else []
    return render_template('candidate/resume_matches.html', resume=data, matches=matches)


@candidate_bp.get('/matches/preview')
def match_preview():
    if not _candidate_is_logged_in():
        abort(401)
    candidate = _candidate_from_session()
    matches = match_open_jobs(candidate.get('cv_text', ''), get_all_jobs(hide_expired=True), limit=3) if candidate and candidate.get('cv_text') else []
    return render_template('candidate/_match_preview.html', matches=matches, has_cv=bool(candidate and candidate.get('cv_text')))
