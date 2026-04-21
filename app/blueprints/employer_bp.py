from flask import Blueprint, request, jsonify, redirect, render_template, session, url_for, flash
from datetime import datetime, timedelta

# Generate and send OTP
from app.services.verification_service import generate_otp, save_verification_otp, send_verification_email
from app.services.employer_service import (
    get_all_employers,
    get_employer_by_id,
    get_employer_by_email,
    create_employer,
    set_employer_verified_status,
    update_employer,
    delete_employer
)
from app.services.job_service import get_jobs_by_employer_id, get_job_by_id, create_job, update_job
from app.services.application_service import (
    get_all_applications_for_employer_jobs,
    get_application_by_id,
    get_applications_by_job_id,
)
from app.services.candidate_service import get_candidate_by_id
from app.services.interview_service import get_interview_by_application_id, get_interview_responses

employer_bp = Blueprint('employer_bp', __name__, url_prefix='/employers')


def _lookup_employer(email):
    """Return employer payload when found, otherwise None."""
    result = get_employer_by_email(email)
    if isinstance(result, tuple):
        payload, status = result
        if status == 404:
            return None
        return payload
    return result


def _employer_is_logged_in():
    return bool(session.get('employer_id')) and not session.get('pending_verification')


def _employer_is_pending_verification():
    return bool(session.get('pending_verification'))


#  GET all employers
@employer_bp.route('/', methods=['GET'])
def fetch_employers():
    result = get_all_employers()
    return jsonify(result), 200


#  GET employer by ID
@employer_bp.route('/<string:employer_id>', methods=['GET'])
def fetch_employer(employer_id):
    result = get_employer_by_id(employer_id)

    # handle tuple response (data, status)
    if isinstance(result, tuple):
        return jsonify(result[0]), result[1]

    return jsonify(result), 200


#  CREATE employer
@employer_bp.route('/', methods=['POST'])
def add_employer():
    data = request.get_json()

    result = create_employer(data)

    if isinstance(result, tuple):
        return jsonify(result[0]), result[1]

    return jsonify(result), 201


#  UPDATE employer
@employer_bp.route('/<string:employer_id>', methods=['PUT'])
def edit_employer(employer_id):
    data = request.get_json()

    result = update_employer(employer_id, data)

    if isinstance(result, tuple):
        return jsonify(result[0]), result[1]

    return jsonify(result), 200


#  DELETE employer
@employer_bp.route('/<string:employer_id>', methods=['DELETE'])
def remove_employer(employer_id):
    result = delete_employer(employer_id)

    if isinstance(result, tuple):
        return jsonify(result[0]), result[1]

    return jsonify(result), 200

#  GET employer by email
@employer_bp.route('/email/<string:email>', methods=['GET'])
def fetch_employer_by_email(email):
    result = get_employer_by_email(email)

    if isinstance(result, tuple):
        return jsonify(result[0]), result[1]

    return jsonify(result), 200


# Register Employer
@employer_bp.route('/register', methods=['POST','GET'])
def register_employer():
    if _employer_is_pending_verification():
        return redirect(url_for('employer_bp.verify_employer'))

    if _employer_is_logged_in():
        return redirect(url_for('employer_bp.employer_dashboard'))

    if request.method == 'GET':
        return render_template('employer/employer_register.html')

    data = {
        'firstName': request.form.get('firstName', '').strip(),
        'lastName': request.form.get('lastName', '').strip(),
        'email': request.form.get('email', '').strip().lower(),
        'phone': request.form.get('phone', '').strip()
    }

    if not data['firstName'] or not data['email']:
        return render_template('employer/employer_register.html', error="First name and email are required")

    # Check for existing employer
    user = _lookup_employer(data['email'])
    if user:
        return render_template('employer/employer_register.html', error="Employer already exists")

    created = create_employer(data)
    if isinstance(created, tuple):
        return render_template('employer/employer_register.html', error=created[0].get('error', 'Registration failed'))

    otp = generate_otp()
    session.pop('login_attempt', None)
    session['employer_id'] = created['id']
    session['employer_email'] = data['email']
    session['verify_email'] = data['email']
    session['pending_verification'] = True
    session['auth_flow'] = 'register'
    session['register_data'] = {
        'firstName': data['firstName'],
        'lastName': data['lastName'],
        'email': data['email'],
        'phone': data['phone'],
        'otp_sent_at': datetime.now().isoformat(),
        'employer_id': created['id']
    }

    if not save_verification_otp(data['email'], otp):
        return render_template('employer/employer_register.html', error="Failed to save OTP")

    if not send_verification_email(data['email'], otp):
        return render_template('employer/employer_register.html', error="Failed to send verification email")

    flash("Verification email sent", "success")
    return redirect(url_for('employer_bp.verify_employer'))


# login User
@employer_bp.route('/login', methods=['POST','GET'])
def login_employer():
    if _employer_is_pending_verification():
        return redirect(url_for('employer_bp.verify_employer'))

    if _employer_is_logged_in():
        return redirect(url_for('employer_bp.employer_dashboard'))

    if request.method == 'GET':
        return render_template('employer/employer_login.html')

    email = request.form.get('email', '').strip().lower()

    if not email:
        return render_template('employer/employer_login.html', error="Email is required")

    # Check if user exists
    user = _lookup_employer(email)
    if not user:
        return render_template('employer/employer_login.html', error="Employer not found")

    # Generate and send OTP
    otp = generate_otp()
    session.pop('register_data', None)
    session['verify_email'] = email
    session['auth_flow'] = 'login'
    session['login_attempt'] = {
        'email': email,
        'timestamp': datetime.now().isoformat()
    }

    if not save_verification_otp(email, otp):
        return render_template('employer/employer_login.html', error="Failed to save OTP")

    if not send_verification_email(email, otp):
        return render_template('employer/employer_login.html', error="Failed to send verification email")

    flash("Verification email sent", "success")
    return redirect(url_for('employer_bp.verify_employer'))


@employer_bp.route('/verify', methods=['POST','GET'])
def verify_employer():
    if _employer_is_logged_in():
        return redirect(url_for('employer_bp.employer_dashboard'))

    if request.method == 'GET':
        return render_template('employer/employer_verify.html')

    user_otp = request.form['otp']
    user_email = session.get('verify_email')

    if not user_email:
        return render_template('employer/employer_verify.html', error="Session expired")

    if not user_otp:
        return render_template('employer/employer_verify.html', error="OTP required")

    # Fetch stored OTP
    from app.services.verification_service import get_otp, delete_verification_otp
    stored_otp = get_otp(user_email)
    if not stored_otp or stored_otp != user_otp:
        return render_template('employer/employer_verify.html', error="Invalid OTP")

    # Delete OTP after successful verification
    delete_verification_otp(user_email)

    # Check if this is registration or login
    auth_flow = session.get('auth_flow')
    register_data = session.get('register_data')
    if auth_flow == 'register' and register_data:
        # Registration already created the employer; verification only activates the session.
        set_employer_verified_status(register_data['employer_id'], True)
        session.pop('register_data', None)
        session.pop('verify_email', None)
        session.pop('auth_flow', None)
        session.pop('pending_verification', None)
        session['employer_id'] = register_data.get('employer_id', session.get('employer_id'))
        session['employer_email'] = register_data['email']

        return redirect(url_for('employer_bp.employer_dashboard'))

    else:
        # Complete login
        user = _lookup_employer(user_email)
        if not user:
            return render_template('employer/employer_verify.html', error="User not found")

        # Set session
        set_employer_verified_status(user['id'], True)
        session.pop('verify_email', None)
        session.pop('login_attempt', None)
        session.pop('auth_flow', None)
        session.pop('pending_verification', None)
        session['employer_id'] = user['id']
        session['employer_email'] = user['email']

        return redirect(url_for('employer_bp.employer_dashboard'))


@employer_bp.route('/resend-otp', methods=['GET'])
def resend_employer_otp():
    email = session.get('verify_email')
    if not email:
        return render_template('employer/employer_verify.html', error="Session expired")

    otp = generate_otp()
    if not save_verification_otp(email, otp):
        return render_template('employer/employer_verify.html', error="Failed to save OTP")

    if not send_verification_email(email, otp):
        return render_template('employer/employer_verify.html', error="Failed to send verification email")

    return render_template('employer/employer_verify.html', success="Verification email resent")


@employer_bp.route('/dashboard', methods=['GET'])
def employer_dashboard():
    if _employer_is_pending_verification():
        return redirect(url_for('employer_bp.verify_employer'))

    if not _employer_is_logged_in():
        return redirect(url_for('employer_bp.login_employer'))

    employer = None
    employer_jobs = []
    employer_applications = []
    employer_applicant_count = 0
    employer_id = session.get('employer_id')
    if employer_id:
        employer_result = get_employer_by_id(employer_id)
        if isinstance(employer_result, tuple):
            employer = employer_result[0]
        else:
            employer = employer_result
        employer_jobs = get_jobs_by_employer_id(employer_id)
        employer_applications = get_all_applications_for_employer_jobs([job['id'] for job in employer_jobs])
        employer_applicant_count = len({application['user_id'] for application in employer_applications if application.get('user_id')})

    return render_template(
        'employer/employer_dashboard.html',
        employer=employer,
        jobs=employer_jobs,
        applications=employer_applications,
        applicant_count=employer_applicant_count
    )


@employer_bp.route('/jobs/new', methods=['GET', 'POST'])
def add_job():
    if _employer_is_pending_verification():
        return redirect(url_for('employer_bp.verify_employer'))

    if not _employer_is_logged_in():
        return redirect(url_for('employer_bp.login_employer'))

    employer = None
    employer_id = session.get('employer_id')
    if employer_id:
        employer_result = get_employer_by_id(employer_id)
        if isinstance(employer_result, tuple):
            employer = employer_result[0]
        else:
            employer = employer_result

    if request.method == 'GET':
        return render_template('employer/employer_job_form.html', employer=employer)

    deadline_value = request.form.get('deadline', '').strip()
    parsed_deadline = None
    if deadline_value:
        try:
            parsed_deadline = datetime.strptime(deadline_value, "%Y-%m-%dT%H:%M")
        except ValueError:
            return render_template('employer/employer_job_form.html', error="Invalid deadline format")

    job_data = {
        "employer_id": session.get("employer_id"),
        "title": request.form.get("title", "").strip(),
        "description": request.form.get("description", "").strip(),
        "skills": request.form.get("skills", "").strip(),
        "experience_level": request.form.get("experience_level", "").strip(),
        "ai_enabled": request.form.get("ai_enabled") == "on",
        "deadline": parsed_deadline,
    }

    result = create_job(job_data)
    if isinstance(result, tuple):
        return render_template(
            'employer/employer_job_form.html',
            employer=employer,
            error=result[0].get('error', 'Failed to create job')
        )

    flash("Job created successfully", "success")
    return redirect(url_for('employer_bp.employer_dashboard'))


@employer_bp.route('/jobs/<string:job_id>', methods=['GET'])
def view_job(job_id):
    if _employer_is_pending_verification():
        return redirect(url_for('employer_bp.verify_employer'))

    if not _employer_is_logged_in():
        return redirect(url_for('employer_bp.login_employer'))

    job = get_job_by_id(job_id)
    if isinstance(job, tuple):
        return render_template('employer/employer_job_detail.html', error=job[0].get('error', 'Job not found'))

    if str(job.get('employer_id')) != str(session.get('employer_id')):
        return render_template('employer/employer_job_detail.html', error="Job not found")

    employer_result = get_employer_by_id(session.get('employer_id'))
    employer = employer_result[0] if isinstance(employer_result, tuple) else employer_result
    return render_template('employer/employer_job_detail.html', employer=employer, job=job)


@employer_bp.route('/jobs/<string:job_id>/edit', methods=['GET', 'POST'])
def edit_job(job_id):
    if _employer_is_pending_verification():
        return redirect(url_for('employer_bp.verify_employer'))

    if not _employer_is_logged_in():
        return redirect(url_for('employer_bp.login_employer'))

    employer_result = get_employer_by_id(session.get('employer_id'))
    employer = employer_result[0] if isinstance(employer_result, tuple) else employer_result

    job = get_job_by_id(job_id)
    if isinstance(job, tuple):
        return render_template('employer/employer_job_form.html', employer=employer, error=job[0].get('error', 'Job not found'))

    if str(job.get('employer_id')) != str(session.get('employer_id')):
        return render_template('employer/employer_job_form.html', employer=employer, error="Job not found")

    if request.method == 'GET':
        return render_template(
            'employer/employer_job_form.html',
            employer=employer,
            job=job,
            form_action=url_for('employer_bp.edit_job', job_id=job_id),
            page_title="Edit Job",
            submit_label="Update Job"
        )

    deadline_value = request.form.get('deadline', '').strip()
    parsed_deadline = None
    if deadline_value:
        try:
            parsed_deadline = datetime.strptime(deadline_value, "%Y-%m-%dT%H:%M")
        except ValueError:
            return render_template(
                'employer/employer_job_form.html',
                employer=employer,
                job=job,
                error="Invalid deadline format",
                form_action=url_for('employer_bp.edit_job', job_id=job_id),
                page_title="Edit Job",
                submit_label="Update Job"
            )

    job_data = {
        "employer_id": session.get("employer_id"),
        "title": request.form.get("title", "").strip(),
        "description": request.form.get("description", "").strip(),
        "skills": request.form.get("skills", "").strip(),
        "experience_level": request.form.get("experience_level", "").strip(),
        "ai_enabled": request.form.get("ai_enabled") == "on",
        "deadline": parsed_deadline,
    }

    result = update_job(job_id, job_data)
    if isinstance(result, tuple):
        return render_template(
            'employer/employer_job_form.html',
            employer=employer,
            job=job,
            error=result[0].get('error', 'Failed to update job'),
            form_action=url_for('employer_bp.edit_job', job_id=job_id),
            page_title="Edit Job",
            submit_label="Update Job"
        )

    flash("Job updated successfully", "success")
    return redirect(url_for('employer_bp.view_job', job_id=job_id))


@employer_bp.route('/profile', methods=['GET'])
def employer_profile():
    if _employer_is_pending_verification():
        return redirect(url_for('employer_bp.verify_employer'))

    if not _employer_is_logged_in():
        return redirect(url_for('employer_bp.login_employer'))

    employer = None
    employer_id = session.get('employer_id')
    if employer_id:
        employer_result = get_employer_by_id(employer_id)
        if isinstance(employer_result, tuple):
            employer = employer_result[0]
        else:
            employer = employer_result

    return render_template('employer/employer_profile.html', employer=employer)


@employer_bp.route('/jobs/<string:job_id>/applications', methods=['GET'])
def view_job_applications(job_id):
    if _employer_is_pending_verification():
        return redirect(url_for('employer_bp.verify_employer'))

    if not _employer_is_logged_in():
        return redirect(url_for('employer_bp.login_employer'))

    employer_result = get_employer_by_id(session.get('employer_id'))
    employer = employer_result[0] if isinstance(employer_result, tuple) else employer_result

    job = get_job_by_id(job_id)
    if isinstance(job, tuple):
        return render_template('employer/employer_job_applications.html', employer=employer, error=job[0].get('error', 'Job not found'))

    if str(job.get('employer_id')) != str(session.get('employer_id')):
        return render_template('employer/employer_job_applications.html', employer=employer, error="Job not found")

    applications = get_applications_by_job_id(job_id)
    application_rows = []
    for application in applications:
        candidate = get_candidate_by_id(application.get('user_id'))
        interview = get_interview_by_application_id(application.get('id'))
        application_rows.append({
            **application,
            'candidate': candidate,
            'interview': interview,
            'interview_score': round(float(interview.get('total_score') or 0) / int(interview.get('response_count') or 1), 2) if interview and int(interview.get('response_count') or 0) else application.get('score', 0),
        })

    return render_template(
        'employer/employer_job_applications.html',
        employer=employer,
        job=job,
        applications=application_rows
    )


@employer_bp.route('/jobs/<string:job_id>/applications/<string:application_id>', methods=['GET'])
def view_job_application_detail(job_id, application_id):
    if _employer_is_pending_verification():
        return redirect(url_for('employer_bp.verify_employer'))

    if not _employer_is_logged_in():
        return redirect(url_for('employer_bp.login_employer'))

    employer_result = get_employer_by_id(session.get('employer_id'))
    employer = employer_result[0] if isinstance(employer_result, tuple) else employer_result

    job = get_job_by_id(job_id)
    if isinstance(job, tuple):
        return render_template('employer/employer_application_detail.html', employer=employer, error=job[0].get('error', 'Job not found'))

    if str(job.get('employer_id')) != str(session.get('employer_id')):
        return render_template('employer/employer_application_detail.html', employer=employer, error="Job not found")

    application = get_application_by_id(application_id)
    if not application or str(application.get('job_id')) != str(job_id):
        return render_template('employer/employer_application_detail.html', employer=employer, error="Application not found")

    candidate = get_candidate_by_id(application.get('user_id'))
    interview = get_interview_by_application_id(application_id)
    interview_responses = get_interview_responses(interview['id']) if interview else []
    interview_average = 0
    if interview and int(interview.get('response_count') or len(interview_responses)):
        interview_average = round(float(interview.get('total_score') or 0) / int(interview.get('response_count') or len(interview_responses)), 2)

    return render_template(
        'employer/employer_application_detail.html',
        employer=employer,
        job=job,
        application=application,
        candidate=candidate,
        interview=interview,
        interview_responses=interview_responses,
        interview_average=interview_average
    )


@employer_bp.route('/candidates/<string:candidate_id>', methods=['GET'])
def view_candidate(candidate_id):
    if _employer_is_pending_verification():
        return redirect(url_for('employer_bp.verify_employer'))

    if not _employer_is_logged_in():
        return redirect(url_for('employer_bp.login_employer'))

    employer_result = get_employer_by_id(session.get('employer_id'))
    employer = employer_result[0] if isinstance(employer_result, tuple) else employer_result
    candidate = get_candidate_by_id(candidate_id)
    if not candidate:
        return render_template('employer/employer_candidate_detail.html', employer=employer, error="Candidate not found")

    return render_template('employer/employer_candidate_detail.html', employer=employer, candidate=candidate)


@employer_bp.route('/profile/edit', methods=['GET', 'POST'])
def edit_employer_profile():
    if _employer_is_pending_verification():
        return redirect(url_for('employer_bp.verify_employer'))

    if not _employer_is_logged_in():
        return redirect(url_for('employer_bp.login_employer'))

    employer_id = session.get('employer_id')
    employer_result = get_employer_by_id(employer_id)
    employer = employer_result[0] if isinstance(employer_result, tuple) else employer_result

    if not employer:
        flash("Employer profile not found", "danger")
        return redirect(url_for('employer_bp.employer_profile'))

    if request.method == 'GET':
        return render_template('employer/employer_profile_edit.html', employer=employer)

    updated_data = {
        'firstName': request.form.get('firstName', '').strip(),
        'lastName': request.form.get('lastName', '').strip(),
        'email': request.form.get('email', '').strip().lower(),
        'phone': request.form.get('phone', '').strip()
    }

    if not updated_data['firstName'] or not updated_data['email']:
        return render_template('employer/employer_profile_edit.html', employer=employer, error="First name and email are required")

    result = update_employer(employer_id, updated_data)
    if isinstance(result, tuple):
        return render_template('employer/employer_profile_edit.html', employer=employer, error=result[0].get('error', 'Failed to update profile'))

    session['employer_email'] = updated_data['email']
    flash("Profile updated successfully", "success")
    return redirect(url_for('employer_bp.employer_profile'))


@employer_bp.route('/logout', methods=['GET'])
def employer_logout():
    session.pop('employer_id', None)
    session.pop('employer_email', None)
    session.pop('verify_email', None)
    session.pop('register_data', None)
    session.pop('login_attempt', None)
    session.pop('auth_flow', None)
    session.pop('pending_verification', None)

    flash("You have been logged out", "success")
    return redirect(url_for('employer_bp.login_employer'))
