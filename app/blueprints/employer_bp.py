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
from app.services.job_taxonomy_service import (
    create_category,
    create_industry,
    get_category_by_id,
    get_grouped_categories,
    get_industries,
    delete_category,
    delete_industry,
    update_category,
    update_industry,
)
from app.services.application_service import (
    get_all_applications_for_employer_jobs,
    get_application_by_id,
    get_applications_by_candidate_id,
    get_applications_by_job_id,
    update_application_resume_analysis,
)
from app.services.candidate_service import get_candidate_by_id
from app.services.interview_service import get_interview_by_application_id, get_interview_responses
from app.services.resume_ai_service import analyze_resume_fit

employer_bp = Blueprint('employer_bp', __name__, url_prefix='/employers')


@employer_bp.before_request
def protect_employer_api():
    api_endpoints = {'fetch_employers', 'fetch_employer', 'fetch_employer_by_email', 'add_employer', 'edit_employer', 'remove_employer'}
    endpoint = (request.endpoint or '').rsplit('.', 1)[-1]
    if endpoint not in api_endpoints:
        return None
    from flask import current_app
    is_admin = bool(session.get('admin_id')) and session.get('admin_email') in current_app.config['ADMIN_EMAILS']
    if is_admin:
        if request.method in {'PUT', 'DELETE', 'POST'}:
            from app.blueprints.auth_bp import check_csrf
            check_csrf()
        return None
    if endpoint in {'fetch_employers', 'add_employer', 'remove_employer'}:
        return jsonify(error='Administrator sign-in required'), 403
    if not _employer_is_logged_in():
        return jsonify(error='Employer sign-in required'), 401
    if request.view_args.get('employer_id') and str(request.view_args['employer_id']) != str(session['employer_id']):
        return jsonify(error='Access denied'), 403
    if request.view_args.get('email') and request.view_args['email'].lower() != session.get('employer_email'):
        return jsonify(error='Access denied'), 403
    if request.method in {'PUT', 'DELETE', 'POST'}:
        from app.blueprints.auth_bp import check_csrf
        check_csrf()


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


def _job_form_context(selected_industry_id=None, job=None):
    return {
        "industries": get_industries(),
        "grouped_categories": get_grouped_categories(),
        "selected_industry_id": selected_industry_id,
        "selected_category_id": job.get('category_id') if job else None,
    }


def _taxonomy_context(selected_industry_id=None, selected_category_id=None):
    grouped_categories = get_grouped_categories()
    return {
        "industries": get_industries(),
        "grouped_categories": grouped_categories,
        "selected_industry_id": selected_industry_id,
        "selected_category_id": selected_category_id,
        "total_categories": sum(len(group["categories"]) for group in grouped_categories),
    }


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

    from app.blueprints.auth_bp import check_csrf
    check_csrf()

    data = {
        'firstName': request.form.get('firstName', '').strip(),
        'lastName': request.form.get('lastName', '').strip(),
        'email': request.form.get('email', '').strip().lower(),
        'phone': request.form.get('phone', '').strip()
    }

    import re
    if len(data['email']) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', data['email']):
        return render_template('employer/employer_register.html', error="Enter a valid email address."), 400

    if not data['firstName'] or not data['email']:
        return render_template('employer/employer_register.html', error="First name and email are required")

    # Check for existing employer
    user = _lookup_employer(data['email'])
    if user:
        return render_template('employer/employer_register.html', error="Employer already exists")

    created = create_employer(data)
    if isinstance(created, tuple):
        return render_template('employer/employer_register.html', error=created[0].get('error', 'Registration failed'))

    from app.blueprints.auth_bp import begin_registration
    return begin_registration("employer", data['email'], created['id'])


# login User
@employer_bp.route('/login', methods=['POST','GET'])
def login_employer():
    from app.blueprints.auth_bp import login
    return login("employer")


@employer_bp.route('/verify', methods=['POST','GET'])
def verify_employer():
    from app.blueprints.auth_bp import verify
    return verify("employer")


@employer_bp.route('/resend-otp', methods=['POST'])
def resend_employer_otp():
    from app.blueprints.auth_bp import resend
    return resend("employer")


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

        # Enrich applications with job and candidate details
        enriched_applications = []
        for application in employer_applications:
            job = get_job_by_id(application.get('job_id'))
            candidate = get_candidate_by_id(application.get('user_id'))
            enriched_applications.append({
                **application,
                'job': job if not isinstance(job, tuple) else None,
                'candidate': candidate if not isinstance(candidate, tuple) else None
            })
        employer_applications = enriched_applications

    return render_template(
        'employer/employer_dashboard.html',
        employer=employer,
        jobs=employer_jobs,
        applications=employer_applications,
        applicant_count=employer_applicant_count
    )


@employer_bp.route('/jobs', methods=['GET'])
def employer_jobs():
    if _employer_is_pending_verification():
        return redirect(url_for('employer_bp.verify_employer'))

    if not _employer_is_logged_in():
        return redirect(url_for('employer_bp.login_employer'))

    employer = None
    employer_jobs = []
    employer_id = session.get('employer_id')
    if employer_id:
        employer_result = get_employer_by_id(employer_id)
        if isinstance(employer_result, tuple):
            employer = employer_result[0]
        else:
            employer = employer_result
        employer_jobs = get_jobs_by_employer_id(employer_id)

    return render_template(
        'employer/employer_jobs.html',
        employer=employer,
        jobs=employer_jobs,
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
        form_context = _job_form_context()
        return render_template('employer/employer_job_form.html', employer=employer, form_data={}, **form_context)

    deadline_value = request.form.get('deadline', '').strip()
    selected_industry_id = request.form.get('industry_id', '').strip() or None
    selected_category_id = request.form.get('category_id', '').strip() or None
    parsed_deadline = None
    if deadline_value:
        try:
            parsed_deadline = datetime.strptime(deadline_value, "%Y-%m-%dT%H:%M")
        except ValueError:
            form_context = _job_form_context(selected_industry_id)
            return render_template('employer/employer_job_form.html', error="Invalid deadline format", employer=employer, form_data=request.form, **form_context)

    selected_category = get_category_by_id(selected_category_id)
    if not selected_category:
        form_context = _job_form_context(selected_industry_id)
        return render_template(
            'employer/employer_job_form.html',
            employer=employer,
            error="Category is required",
            form_data=request.form,
            **form_context
        )

    if selected_industry_id and str(selected_category.get('industry_id')) != str(selected_industry_id):
        form_context = _job_form_context(selected_industry_id)
        return render_template(
            'employer/employer_job_form.html',
            employer=employer,
            error="Selected category does not belong to the selected industry",
            form_data=request.form,
            **form_context
        )

    job_data = {
        "employer_id": session.get("employer_id"),
        "category_id": selected_category_id,
        "title": request.form.get("title", "").strip(),
        "description": request.form.get("description", "").strip(),
        "responsibilities": request.form.get("responsibilities", "").strip(),
        "requirements": request.form.get("requirements", "").strip(),
        "who_should_apply": request.form.get("who_should_apply", "").strip(),
        "salary_insight": request.form.get("salary_insight", "").strip(),
        "location": request.form.get("location", "").strip(),
        "skills": request.form.get("skills", "").strip(),
        "experience_level": request.form.get("experience_level", "").strip(),
        "ai_enabled": request.form.get("ai_enabled") == "on",
        "is_technical": request.form.get("is_technical") == "on",
        "resume_required": request.form.get("resume_required") == "on",
        "deadline": parsed_deadline,
    }

    result = create_job(job_data)
    if isinstance(result, tuple):
        form_context = _job_form_context(selected_category.get('industry_id'))
        return render_template(
            'employer/employer_job_form.html',
            employer=employer,
            error=result[0].get('error', 'Failed to create job'),
            form_data=request.form,
            **form_context
        )

    flash("Job created successfully", "success")
    return redirect(url_for('employer_bp.employer_dashboard'))


@employer_bp.route('/taxonomy', methods=['GET'])
def manage_taxonomy():
    if _employer_is_pending_verification():
        return redirect(url_for('employer_bp.verify_employer'))

    if not _employer_is_logged_in():
        return redirect(url_for('employer_bp.login_employer'))

    employer_result = get_employer_by_id(session.get('employer_id'))
    employer = employer_result[0] if isinstance(employer_result, tuple) else employer_result
    return render_template(
        'employer/employer_taxonomy.html',
        employer=employer,
        **_taxonomy_context()
    )


@employer_bp.route('/taxonomy/industries', methods=['POST'])
def create_taxonomy_industry():
    if _employer_is_pending_verification():
        return redirect(url_for('employer_bp.verify_employer'))

    if not _employer_is_logged_in():
        return redirect(url_for('employer_bp.login_employer'))

    name = request.form.get('name', '').strip()
    result = create_industry(name)
    if isinstance(result, tuple):
        flash(result[0].get('error', 'Failed to create industry'), 'danger')
    else:
        flash("Industry created successfully", "success")
    return redirect(url_for('employer_bp.manage_taxonomy'))


@employer_bp.route('/taxonomy/industries/<string:industry_id>/edit', methods=['POST'])
def edit_taxonomy_industry(industry_id):
    if _employer_is_pending_verification():
        return redirect(url_for('employer_bp.verify_employer'))

    if not _employer_is_logged_in():
        return redirect(url_for('employer_bp.login_employer'))

    name = request.form.get('name', '').strip()
    result = update_industry(industry_id, name)
    if isinstance(result, tuple):
        flash(result[0].get('error', 'Failed to update industry'), 'danger')
    else:
        flash("Industry updated successfully", "success")
    return redirect(url_for('employer_bp.manage_taxonomy'))


@employer_bp.route('/taxonomy/industries/<string:industry_id>/delete', methods=['POST'])
def remove_taxonomy_industry(industry_id):
    if _employer_is_pending_verification():
        return redirect(url_for('employer_bp.verify_employer'))

    if not _employer_is_logged_in():
        return redirect(url_for('employer_bp.login_employer'))

    result = delete_industry(industry_id)
    if isinstance(result, tuple):
        flash(result[0].get('error', 'Failed to delete industry'), 'danger')
    else:
        flash("Industry deleted successfully", "success")
    return redirect(url_for('employer_bp.manage_taxonomy'))


@employer_bp.route('/taxonomy/categories', methods=['POST'])
def create_taxonomy_category():
    if _employer_is_pending_verification():
        return redirect(url_for('employer_bp.verify_employer'))

    if not _employer_is_logged_in():
        return redirect(url_for('employer_bp.login_employer'))

    industry_id = request.form.get('industry_id', '').strip()
    name = request.form.get('name', '').strip()
    result = create_category(industry_id, name)
    if isinstance(result, tuple):
        flash(result[0].get('error', 'Failed to create category'), 'danger')
    else:
        flash("Category created successfully", "success")
    return redirect(url_for('employer_bp.manage_taxonomy'))


@employer_bp.route('/taxonomy/categories/<string:category_id>/edit', methods=['POST'])
def edit_taxonomy_category(category_id):
    if _employer_is_pending_verification():
        return redirect(url_for('employer_bp.verify_employer'))

    if not _employer_is_logged_in():
        return redirect(url_for('employer_bp.login_employer'))

    industry_id = request.form.get('industry_id', '').strip()
    name = request.form.get('name', '').strip()
    result = update_category(category_id, industry_id, name)
    if isinstance(result, tuple):
        flash(result[0].get('error', 'Failed to update category'), 'danger')
    else:
        flash("Category updated successfully", "success")
    return redirect(url_for('employer_bp.manage_taxonomy'))


@employer_bp.route('/taxonomy/categories/<string:category_id>/delete', methods=['POST'])
def remove_taxonomy_category(category_id):
    if _employer_is_pending_verification():
        return redirect(url_for('employer_bp.verify_employer'))

    if not _employer_is_logged_in():
        return redirect(url_for('employer_bp.login_employer'))

    result = delete_category(category_id)
    if isinstance(result, tuple):
        flash(result[0].get('error', 'Failed to delete category'), 'danger')
    else:
        flash("Category deleted successfully", "success")
    return redirect(url_for('employer_bp.manage_taxonomy'))


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
        form_context = _job_form_context()
        return render_template('employer/employer_job_form.html', employer=employer, error=job[0].get('error', 'Job not found'), form_data={}, **form_context)

    if str(job.get('employer_id')) != str(session.get('employer_id')):
        form_context = _job_form_context()
        return render_template('employer/employer_job_form.html', employer=employer, error="Job not found", form_data={}, **form_context)

    if request.method == 'GET':
        selected_industry_id = job.get('industry_id') or (job.get('category_id') and job.get('industry_id'))
        form_context = _job_form_context(selected_industry_id, job=job)
        return render_template(
            'employer/employer_job_form.html',
            employer=employer,
            job=job,
            form_data={},
            form_action=url_for('employer_bp.edit_job', job_id=job_id),
            page_title="Edit Job",
            submit_label="Update Job",
            **form_context
        )

    deadline_value = request.form.get('deadline', '').strip()
    selected_industry_id = request.form.get('industry_id', '').strip() or None
    selected_category_id = request.form.get('category_id', '').strip() or None
    parsed_deadline = None
    if deadline_value:
        try:
            parsed_deadline = datetime.strptime(deadline_value, "%Y-%m-%dT%H:%M")
        except ValueError:
            form_context = _job_form_context(selected_industry_id)
            return render_template(
                'employer/employer_job_form.html',
                employer=employer,
                job=job,
                error="Invalid deadline format",
                form_data=request.form,
                form_action=url_for('employer_bp.edit_job', job_id=job_id),
                page_title="Edit Job",
                submit_label="Update Job",
                **form_context
            )

    selected_category = get_category_by_id(selected_category_id)
    if not selected_category:
        form_context = _job_form_context(selected_industry_id)
        return render_template(
            'employer/employer_job_form.html',
            employer=employer,
            job=job,
            error="Category is required",
            form_data=request.form,
            form_action=url_for('employer_bp.edit_job', job_id=job_id),
            page_title="Edit Job",
            submit_label="Update Job",
            **form_context
        )

    if selected_industry_id and str(selected_category.get('industry_id')) != str(selected_industry_id):
        form_context = _job_form_context(selected_industry_id)
        return render_template(
            'employer/employer_job_form.html',
            employer=employer,
            job=job,
            error="Selected category does not belong to the selected industry",
            form_data=request.form,
            form_action=url_for('employer_bp.edit_job', job_id=job_id),
            page_title="Edit Job",
            submit_label="Update Job",
            **form_context
        )

    job_data = {
        "employer_id": session.get("employer_id"),
        "category_id": selected_category_id,
        "title": request.form.get("title", "").strip(),
        "description": request.form.get("description", "").strip(),
        "responsibilities": request.form.get("responsibilities", "").strip(),
        "requirements": request.form.get("requirements", "").strip(),
        "who_should_apply": request.form.get("who_should_apply", "").strip(),
        "salary_insight": request.form.get("salary_insight", "").strip(),
        "location": request.form.get("location", "").strip(),
        "skills": request.form.get("skills", "").strip(),
        "experience_level": request.form.get("experience_level", "").strip(),
        "ai_enabled": request.form.get("ai_enabled") == "on",
        "is_technical": request.form.get("is_technical") == "on",
        "resume_required": request.form.get("resume_required") == "on",
        "deadline": parsed_deadline,
    }

    result = update_job(job_id, job_data)
    if isinstance(result, tuple):
        form_context = _job_form_context(selected_category.get('industry_id'), job=job)
        return render_template(
            'employer/employer_job_form.html',
            employer=employer,
            job=job,
            error=result[0].get('error', 'Failed to update job'),
            form_data=request.form,
            form_action=url_for('employer_bp.edit_job', job_id=job_id),
            page_title="Edit Job",
            submit_label="Update Job",
            **form_context
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
    if candidate and application.get("resume_path") and not application.get("resume_ai_fit") and not application.get("resume_ai_summary"):
        analysis = analyze_resume_fit(job, candidate, application.get("resume_path"))
        update_application_resume_analysis(application_id, analysis)
        application = get_application_by_id(application_id)
    interview = get_interview_by_application_id(application_id)
    interview_responses = get_interview_responses(interview['id']) if interview else []
    interview_average = 0
    if interview and int(interview.get('response_count') or len(interview_responses)):
        interview_average = round(float(interview.get('total_score') or 0) / int(interview.get('response_count') or len(interview_responses)), 2)

    if any(response.get("score") is None for response in interview_responses):
        interview_average = "Pending feedback"
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

    applications = get_applications_by_candidate_id(candidate_id)

    # Enrich applications with job details
    applications_with_jobs = []
    for application in applications:
        job = get_job_by_id(application.get('job_id'))
        if not isinstance(job, tuple):
            applications_with_jobs.append({
                **application,
                'job': job
            })
        else:
            applications_with_jobs.append(application)

    resume_applications = [application for application in applications_with_jobs if application.get("resume_path")]

    return render_template(
        'employer/employer_candidate_detail.html',
        employer=employer,
        candidate=candidate,
        applications=applications_with_jobs,
        resume_applications=resume_applications,
    )


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
    session.pop('employer_challenge', None)
    session.pop('employer_id', None)
    session.pop('employer_email', None)
    session.pop('verify_email', None)
    session.pop('register_data', None)
    session.pop('login_attempt', None)
    session.pop('auth_flow', None)
    session.pop('pending_verification', None)

    flash("You have been logged out", "success")
    return redirect(url_for('employer_bp.login_employer'))
