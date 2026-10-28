import os
import uuid
from datetime import datetime

from werkzeug.utils import secure_filename

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, current_app, abort, send_from_directory
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.services.job_service import get_all_jobs, get_job_by_id
from app.services.candidate_service import get_candidate_by_email, get_candidate_by_id, get_or_create_candidate
from app.services.application_service import (
    get_application_by_candidate_and_job,
    get_application_by_id,
    get_applications_by_job_id,
    submit_application,
    update_application_status,
    update_application_status_and_score,
)
from app.services.saved_job_service import (
    get_saved_job_by_candidate_and_job,
    save_job_for_candidate,
    unsave_job_for_candidate,
)
from app.services.job_taxonomy_service import get_grouped_categories, get_industries, get_category_by_id, get_industry_by_id
from app.services.resume_ai_service import analyze_resume_fit
from app.services.candidate_resume_service import cv_directory, find_profile_cv, find_application_resume
from app.services.interview_service import (
    add_interview_response_once,
    evaluate_saved_response,
    interview_summary,
    get_question_plan,
    complete_interview,
    create_interview,
    get_interview_by_application_id,
    get_interview_by_id,
    get_interview_responses,
)
from app.services.verification_service import send_application_submission_email, send_interview_invitation_email

jobs_bp = Blueprint('jobs_bp', __name__)
AI_INTERVIEW_QUESTION_LIMIT = 15
INTERVIEW_LINK_MAX_AGE_SECONDS = 60 * 60 * 24
EXPERIENCE_LEVEL_OPTIONS = [
    "Internship",
    "Entry Level",
    "Junior",
    "Mid Level",
    "Senior",
    "Lead",
    "Executive",
]
ALLOWED_RESUME_EXTENSIONS = {"pdf", "doc", "docx"}


def _interview_link_serializer():
    return URLSafeTimedSerializer(current_app.secret_key, salt="candidate-interview-link")


def _generate_interview_link_token(candidate_id, job_id):
    return _interview_link_serializer().dumps({
        "candidate_id": candidate_id,
        "job_id": job_id,
    })


def _decode_interview_link_token(token):
    try:
        return _interview_link_serializer().loads(token, max_age=INTERVIEW_LINK_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None


def _send_application_and_interview_emails(candidate, job, job_id):
    candidate_name = " ".join(
        part for part in [candidate.get("first_name"), candidate.get("last_name")] if part
    ).strip()

    send_application_submission_email(
        candidate.get("email"),
        candidate_name,
        job.get("title"),
        url_for('jobs_bp.job_detail', job_id=job_id, _external=True),
    )

    if not job.get("ai_enabled"):
        return

    interview_link = url_for(
        'jobs_bp.job_interview',
        job_id=job_id,
        token=_generate_interview_link_token(candidate["id"], job_id),
        _external=True,
    )
    send_interview_invitation_email(
        candidate.get("email"),
        candidate_name,
        job.get("title"),
        interview_link,
    )


def _job_is_expired(job):
    deadline = job.get("deadline")
    if not deadline:
        return False
    try:
        return deadline <= datetime.now()
    except TypeError:
        return False


def _resume_upload_allowed(filename):
    if not filename or "." not in filename:
        return False
    extension = filename.rsplit(".", 1)[1].lower()
    return extension in ALLOWED_RESUME_EXTENSIONS


def _save_resume_upload(upload, candidate_id, job_id):
    if not upload or not upload.filename:
        return None

    if not _resume_upload_allowed(upload.filename):
        return {"error": "Resume must be a PDF, DOC, or DOCX file"}

    upload_dir = str(cv_directory())
    os.makedirs(upload_dir, exist_ok=True)

    original_name = secure_filename(upload.filename)
    unique_name = f"{candidate_id}_{job_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{original_name}"
    file_path = os.path.join(upload_dir, unique_name)
    upload.save(file_path)

    return {
        "resume_path": f"candidate_cvs/{unique_name}",
        "resume_name": original_name,
    }


@jobs_bp.route('/jobs', endpoint='browse_jobs')
@jobs_bp.route('/')
def index():
    selected_industry_id = request.args.get('industry_id', '').strip() or None
    selected_category_id = request.args.get('category_id', '').strip() or None
    selected_experience_level = request.args.get('experience_level', '').strip() or None
    jobs = get_all_jobs(
        industry_id=selected_industry_id,
        category_id=selected_category_id,
        experience_level=selected_experience_level,
        hide_expired=True,
    )
    search_query = request.args.get('q', '').strip()[:200]
    if search_query:
        words = search_query.casefold().split()
        jobs = [job for job in jobs if all(word in ' '.join(str(job.get(field) or '') for field in ('title', 'skills', 'industry_name', 'category_name', 'description', 'responsibilities', 'requirements', 'who_should_apply', 'location')).casefold() for word in words)]
    industries = get_industries()
    grouped_categories = get_grouped_categories()
    selected_category = get_category_by_id(selected_category_id) if selected_category_id else None
    selected_industry = get_industry_by_id(selected_industry_id) if selected_industry_id else None
    total_jobs = len(jobs)
    total_pages = max(1, (total_jobs + 19) // 20)
    page = max(1, min(request.args.get('page', 1, type=int), total_pages))
    browsing = request.endpoint == 'jobs_bp.browse_jobs'
    def pagination_url(number):
        return url_for('jobs_bp.browse_jobs', q=search_query, industry_id=selected_industry_id,
                       category_id=selected_category_id, experience_level=selected_experience_level, page=number)
    return render_template(
        'jobs/browse_jobs.html' if browsing else 'jobs/jobs.html',
        total_jobs=total_jobs, total_pages=total_pages, page=page, pagination_url=pagination_url,
        range_start=((page - 1) * 20 + 1) if total_jobs else 0,
        range_end=min(page * 20, total_jobs),
        search_query=search_query,
        jobs=jobs[(page - 1) * 20:page * 20] if browsing else jobs,
        industries=industries,
        grouped_categories=grouped_categories,
        selected_industry_id=selected_industry_id,
        selected_category_id=selected_category_id,
        selected_experience_level=selected_experience_level,
        selected_category=selected_category,
        selected_industry=selected_industry,
        experience_levels=EXPERIENCE_LEVEL_OPTIONS,
    )


@jobs_bp.route('/<string:job_id>')
@jobs_bp.route('/jobs/<string:job_id>')
def job_detail(job_id):
    job = get_job_by_id(job_id)
    if isinstance(job, tuple):
        return render_template('jobs/job_detail.html', error=job[0].get('error', 'Job not found'))
    if _job_is_expired(job):
        return render_template('jobs/job_detail.html', error='This job posting has expired')

    candidate = None
    candidate_application = None
    saved_job = None
    candidate_id = session.get('candidate_id')
    if candidate_id:
        candidate = get_candidate_by_id(candidate_id)
        if not candidate:
            session.pop('candidate_id', None)
            session.pop('candidate_email', None)
        else:
            candidate_application = get_application_by_candidate_and_job(candidate_id, job_id)
            saved_job = get_saved_job_by_candidate_and_job(candidate_id, job_id)
    return render_template(
        'jobs/job_detail.html',
        job=job,
        candidate=candidate,
        candidate_application=candidate_application,
        saved_job=saved_job,
    )


@jobs_bp.route('/<string:job_id>/save', methods=['POST'])
def toggle_saved_job(job_id):
    job = get_job_by_id(job_id)
    if isinstance(job, tuple):
        return render_template('jobs/job_detail.html', error=job[0].get('error', 'Job not found'))

    candidate_id = session.get('candidate_id')
    if not candidate_id:
        flash("Please log in to save jobs", "warning")
        return redirect(url_for('candidate_bp.login_candidate', next=url_for('jobs_bp.job_detail', job_id=job_id)))

    candidate = get_candidate_by_id(candidate_id)
    if not candidate:
        session.pop('candidate_id', None)
        session.pop('candidate_email', None)
        flash("Please log in to save jobs", "warning")
        return redirect(url_for('candidate_bp.login_candidate', next=url_for('jobs_bp.job_detail', job_id=job_id)))

    saved_job = get_saved_job_by_candidate_and_job(candidate_id, job_id)
    if saved_job:
        result = unsave_job_for_candidate(candidate_id, job_id)
        if isinstance(result, tuple):
            flash(result[0].get('error', 'Failed to remove saved job'), "danger")
        else:
            flash("Removed from saved jobs", "success")
    else:
        result = save_job_for_candidate(candidate_id, job_id)
        if isinstance(result, tuple):
            flash(result[0].get('error', 'Failed to save job'), "danger")
        else:
            flash("Added to saved jobs", "success")

    return redirect(url_for('jobs_bp.job_detail', job_id=job_id))


@jobs_bp.route('/<string:job_id>/apply', methods=['GET', 'POST'])
def job_apply(job_id):
    job = get_job_by_id(job_id)
    if isinstance(job, tuple):
        return render_template('jobs/job_apply.html', error=job[0].get('error', 'Job not found'))
    if _job_is_expired(job):
        return render_template('jobs/job_apply.html', error='This job posting has expired')

    candidate = None
    candidate_application = None
    candidate_id = session.get('candidate_id')
    if candidate_id:
        candidate = get_candidate_by_id(candidate_id)
        if candidate:
            candidate_application = get_application_by_candidate_and_job(candidate_id, job_id)

    if candidate_application:
        return render_template(
            'jobs/job_apply.html',
            job=job,
            candidate=candidate,
            candidate_application=candidate_application,
            already_applied=True,
        )

    if request.method == 'GET':
        return render_template('jobs/job_apply.html', job=job, candidate=candidate, candidate_application=candidate_application)

    resume_upload = request.files.get("resume")
    use_profile_cv = bool(candidate and candidate.get("cv_filename") and request.form.get("use_profile_cv") == "on")
    if job.get("resume_required") and (not resume_upload or not resume_upload.filename) and not use_profile_cv:
        return render_template('jobs/job_apply.html', job=job, candidate=candidate, error="Resume upload is required for this job", candidate_application=candidate_application)
    if resume_upload and resume_upload.filename and not _resume_upload_allowed(resume_upload.filename):
        return render_template('jobs/job_apply.html', job=job, candidate=candidate, error="Resume must be a PDF, DOC, or DOCX file", candidate_application=candidate_application)

    candidate_data = {
        "first_name": request.form.get("first_name", "").strip(),
        "last_name": request.form.get("last_name", "").strip(),
        "email": request.form.get("email", "").strip().lower(),
        "phone": request.form.get("phone", "").strip(),
    }

    if not candidate_data["first_name"] or not candidate_data["email"]:
        return render_template('jobs/job_apply.html', job=job, error="First name and email are required")

    candidate = get_or_create_candidate(candidate_data)
    if isinstance(candidate, tuple):
        return render_template('jobs/job_apply.html', job=job, error=candidate[0].get('error', 'Failed to create candidate'))

    resume_result = _save_resume_upload(resume_upload, candidate["id"], job_id)
    if not resume_result and use_profile_cv:
        if str(session.get("candidate_id")) != str(candidate["id"]) or not candidate.get("cv_filename"):
            abort(403)
        if not find_profile_cv(candidate["cv_filename"], cv_directory()):
            return render_template('jobs/job_apply.html' if request.endpoint == 'jobs_bp.job_apply' else 'jobs/job_easy_apply.html',
                                   job=job, candidate=candidate,
                                   error="Your saved CV is unavailable. Please upload it again.")
        resume_result = {"resume_path": "candidate_cvs/" + candidate["cv_filename"],
                         "resume_name": candidate.get("cv_name") or "Resume"}
    if resume_result and resume_result.get("error"):
        return render_template('jobs/job_apply.html', job=job, candidate=candidate, error=resume_result["error"], candidate_application=candidate_application)

    resume_analysis = None
    if resume_result:
        resume_analysis = analyze_resume_fit(job, candidate, resume_result.get("resume_path"))

    application_result = submit_application({
        "job_id": job_id,
        "user_id": candidate["id"],
        "status": "submitted",
        "score": 0,
        "resume_path": resume_result.get("resume_path") if resume_result else None,
        "resume_name": resume_result.get("resume_name") if resume_result else None,
        "resume_required": bool(job.get("resume_required")),
        "resume_ai_score": resume_analysis.get("score", 0) if resume_analysis else 0,
        "resume_ai_fit": resume_analysis.get("fit_label") if resume_analysis else None,
        "resume_ai_summary": resume_analysis.get("summary") if resume_analysis else None,
        "resume_ai_strengths": resume_analysis.get("strengths") if resume_analysis else None,
        "resume_ai_gaps": resume_analysis.get("gaps") if resume_analysis else None,
        "resume_ai_recommendation": resume_analysis.get("recommendation") if resume_analysis else None,
        "resume_ai_source": resume_analysis.get("source") if resume_analysis else None,
        "resume_ai_analyzed_at": resume_analysis.get("analyzed_at") if resume_analysis else None,
    })

    if isinstance(application_result, tuple):
        return render_template('jobs/job_apply.html', job=job, error=application_result[0].get('error', 'Failed to submit application'))

    _send_application_and_interview_emails(candidate, job, job_id)

    flash("Application submitted successfully", "success")
    return redirect(url_for('jobs_bp.job_detail', job_id=job_id))


@jobs_bp.route('/<string:job_id>/easy-apply', methods=['GET', 'POST'])
def job_easy_apply(job_id):
    job = get_job_by_id(job_id)
    if isinstance(job, tuple):
        return render_template('jobs/job_easy_apply.html', error=job[0].get('error', 'Job not found'))
    if _job_is_expired(job):
        return render_template('jobs/job_easy_apply.html', error='This job posting has expired')

    candidate_id = session.get('candidate_id')
    candidate = get_candidate_by_id(candidate_id) if candidate_id else None
    if not candidate:
        session.pop('candidate_id', None)
        session.pop('candidate_email', None)
        return render_template(
            'jobs/job_easy_apply.html',
            job=job,
            candidate=None,
            requires_login=True,
            login_url=url_for('candidate_bp.login_candidate', next=url_for('jobs_bp.job_easy_apply', job_id=job_id)),
            register_url=url_for('candidate_bp.register_candidate', next=url_for('jobs_bp.job_easy_apply', job_id=job_id)),
        )

    candidate_application = get_application_by_candidate_and_job(candidate["id"], job_id)
    if candidate_application:
        return render_template(
            'jobs/job_easy_apply.html',
            job=job,
            candidate=candidate,
            candidate_application=candidate_application,
            already_applied=True,
        )

    if request.method == 'GET':
        return render_template('jobs/job_easy_apply.html', job=job, candidate=candidate, candidate_application=candidate_application)

    resume_upload = request.files.get("resume")
    use_profile_cv = bool(candidate and candidate.get("cv_filename") and request.form.get("use_profile_cv") == "on")
    if job.get("resume_required") and (not resume_upload or not resume_upload.filename) and not use_profile_cv:
        return render_template(
            'jobs/job_easy_apply.html',
            job=job,
            candidate=candidate,
            error="Resume upload is required for this job",
            candidate_application=candidate_application
        )
    if resume_upload and resume_upload.filename and not _resume_upload_allowed(resume_upload.filename):
        return render_template(
            'jobs/job_easy_apply.html',
            job=job,
            candidate=candidate,
            error="Resume must be a PDF, DOC, or DOCX file",
            candidate_application=candidate_application
        )

    resume_result = _save_resume_upload(resume_upload, candidate["id"], job_id)
    if not resume_result and use_profile_cv:
        if str(session.get("candidate_id")) != str(candidate["id"]) or not candidate.get("cv_filename"):
            abort(403)
        if not find_profile_cv(candidate["cv_filename"], cv_directory()):
            return render_template('jobs/job_apply.html' if request.endpoint == 'jobs_bp.job_apply' else 'jobs/job_easy_apply.html',
                                   job=job, candidate=candidate,
                                   error="Your saved CV is unavailable. Please upload it again.")
        resume_result = {"resume_path": "candidate_cvs/" + candidate["cv_filename"],
                         "resume_name": candidate.get("cv_name") or "Resume"}
    if resume_result and resume_result.get("error"):
        return render_template(
            'jobs/job_easy_apply.html',
            job=job,
            candidate=candidate,
            error=resume_result["error"],
            candidate_application=candidate_application
        )

    resume_analysis = None
    if resume_result:
        resume_analysis = analyze_resume_fit(job, candidate, resume_result.get("resume_path"))

    application_result = submit_application({
        "job_id": job_id,
        "user_id": candidate["id"],
        "status": "submitted",
        "score": 0,
        "resume_path": resume_result.get("resume_path") if resume_result else None,
        "resume_name": resume_result.get("resume_name") if resume_result else None,
        "resume_required": bool(job.get("resume_required")),
        "resume_ai_score": resume_analysis.get("score", 0) if resume_analysis else 0,
        "resume_ai_fit": resume_analysis.get("fit_label") if resume_analysis else None,
        "resume_ai_summary": resume_analysis.get("summary") if resume_analysis else None,
        "resume_ai_strengths": resume_analysis.get("strengths") if resume_analysis else None,
        "resume_ai_gaps": resume_analysis.get("gaps") if resume_analysis else None,
        "resume_ai_recommendation": resume_analysis.get("recommendation") if resume_analysis else None,
        "resume_ai_source": resume_analysis.get("source") if resume_analysis else None,
        "resume_ai_analyzed_at": resume_analysis.get("analyzed_at") if resume_analysis else None,
    })

    if isinstance(application_result, tuple):
        return render_template(
            'jobs/job_easy_apply.html',
            job=job,
            candidate=candidate,
            error=application_result[0].get('error', 'Failed to submit application')
        )

    _send_application_and_interview_emails(candidate, job, job_id)

    flash("Easy application submitted successfully", "success")
    return redirect(url_for('jobs_bp.job_detail', job_id=job_id))


@jobs_bp.route('/<string:job_id>/interview', methods=['GET'])
def job_interview(job_id):
    job = get_job_by_id(job_id)
    if isinstance(job, tuple):
        return render_template('jobs/job_interview.html', error=job[0].get('error', 'Job not found'))
    # Closing a posting stops new applications, not existing applicants' interviews.

    interview_token = request.args.get("token", "").strip()
    signed_in_candidate = get_candidate_by_id(session["candidate_id"]) if session.get("candidate_id") else None
    prefill_email = signed_in_candidate.get("email") if signed_in_candidate else None
    auto_start = bool(signed_in_candidate and request.args.get("start") == "1")
    if interview_token:
        token_data = _decode_interview_link_token(interview_token)
        if token_data and str(token_data.get("job_id")) == str(job_id):
            candidate = get_candidate_by_id(token_data.get("candidate_id"))
            if candidate:
                prefill_email = candidate.get("email")
                auto_start = True

    return render_template(
        'jobs/job_interview.html',
        job=job,
        interview_prefill_email=prefill_email,
        interview_auto_start=auto_start,
    )


@jobs_bp.route('/<string:job_id>/interview/start', methods=['POST'])
def job_interview_start(job_id):
    job = get_job_by_id(job_id)
    if isinstance(job, tuple):
        return jsonify({"error": job[0].get('error', 'Job not found')}), 404

    ai_enabled = bool(job.get("ai_enabled"))
    if not ai_enabled:
        return jsonify({"error": "AI interview is not enabled for this job"}), 400

    data = request.get_json(silent=True) or request.form
    email = (data.get("email") or "").strip().lower()
    if not email:
        return jsonify({"error": "Email is required"}), 400

    candidate = get_candidate_by_email(email)
    if not candidate:
        return jsonify({"error": "No candidate account found for that email"}), 404

    token_data = _decode_interview_link_token(str(data.get("token") or "")) if data.get("token") else None
    invited = token_data and str(token_data.get("candidate_id")) == str(candidate["id"]) and str(token_data.get("job_id")) == str(job_id)
    if str(session.get("candidate_id") or "") != str(candidate["id"]) and not invited:
        return jsonify({"error": "Sign in with this candidate account or use your interview invitation link."}), 403

    application = get_application_by_candidate_and_job(candidate["id"], job_id)
    if not application:
        return jsonify({"error": "Please apply for this job before starting the AI interview"}), 400

    existing_interview = get_interview_by_application_id(application["id"])
    if existing_interview and existing_interview.get("status") == "completed":
        return jsonify({"error": "This interview has already been completed"}), 400

    interview = existing_interview
    if not interview:
        interview = create_interview({
            "application_id": application["id"],
            "candidate_id": candidate["id"],
            "role": job.get("title"),
            "total_score": 0,
            "response_count": 0,
            "status": "in_progress",
        })

    if application.get("status") == "submitted":
        update_application_status(application["id"], "interview_in_progress")
    session["active_interview"] = {"id": interview["id"], "job_id": job_id}
    responses = get_interview_responses(interview["id"])
    if len(responses) >= AI_INTERVIEW_QUESTION_LIMIT:
        summary = interview_summary(responses)
        total_score, response_count, average_score = summary["total_score"], summary["responses"], summary["average_score"]
        complete_interview(interview["id"])
        if interview.get("application_id"):
            update_application_status_and_score(
                interview.get("application_id"),
                "interview_completed",
                average_score,
            )
        return jsonify({
            "finished": True,
            "message": "Interview already completed",
            "total_score": total_score,
            "average_score": average_score,
            "responses": response_count,
        })

    try:
        slot = get_question_plan(interview, job, AI_INTERVIEW_QUESTION_LIMIT)[len(responses)]
        question = slot["question"]
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503

    return jsonify({
        "interview_id": interview["id"],
        "question": question,
        "question_type": slot["type"],
        "focus": slot["focus"],
        "coverage": slot["coverage"],
        "question_number": len(responses) + 1,
        "question_limit": AI_INTERVIEW_QUESTION_LIMIT,
    })


@jobs_bp.route('/<string:job_id>/interviews/<string:interview_id>/question', methods=['POST'])
def job_interview_question(job_id, interview_id):
    job = get_job_by_id(job_id)
    if isinstance(job, tuple):
        return jsonify({"error": job[0].get('error', 'Job not found')}), 404

    active = session.get("active_interview") or {}
    if active.get("id") != interview_id or active.get("job_id") != job_id:
        return jsonify({"error": "Please start this interview in this browser first"}), 403

    interview = get_interview_by_id(interview_id)
    if not interview:
        return jsonify({"error": "Interview not found"}), 404

    if interview.get("status") == "completed":
        return jsonify({"error": "Interview already completed"}), 400

    responses = get_interview_responses(interview_id)
    if len(responses) >= AI_INTERVIEW_QUESTION_LIMIT:
        summary = interview_summary(responses)
        total_score, response_count, average_score = summary["total_score"], summary["responses"], summary["average_score"]
        complete_interview(interview_id)
        if interview.get("application_id"):
            update_application_status_and_score(
                interview.get("application_id"),
                "interview_completed",
                average_score,
            )
        return jsonify({
            "finished": True,
            "message": "Interview already completed",
            "total_score": total_score,
            "average_score": average_score,
            "responses": response_count,
        })

    try:
        slot = get_question_plan(interview, job, AI_INTERVIEW_QUESTION_LIMIT)[len(responses)]
        question = slot["question"]
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503

    return jsonify({
        "question": question,
        "question_type": slot["type"],
        "focus": slot["focus"],
        "coverage": slot["coverage"],
        "question_number": len(responses) + 1,
        "question_limit": AI_INTERVIEW_QUESTION_LIMIT,
    })


@jobs_bp.route('/<string:job_id>/interviews/<string:interview_id>/answer', methods=['POST'])
def job_interview_answer(job_id, interview_id):
    job = get_job_by_id(job_id)
    if isinstance(job, tuple):
        return jsonify({"error": job[0].get('error', 'Job not found')}), 404

    active = session.get("active_interview") or {}
    if active.get("id") != interview_id or active.get("job_id") != job_id:
        return jsonify({"error": "Please start this interview in this browser first"}), 403

    interview = get_interview_by_id(interview_id)
    if not interview:
        return jsonify({"error": "Interview not found"}), 404

    if interview.get("status") == "completed":
        return jsonify({"error": "Interview already completed"}), 400

    data = request.get_json(silent=True) or request.form
    question = (data.get("question") or "").strip()
    answer = data.get("answer") or ""

    if not isinstance(answer, str) or not question or not answer.strip():
        return jsonify({"error": "Question and answer are required"}), 400

    responses = get_interview_responses(interview_id)
    if len(responses) >= AI_INTERVIEW_QUESTION_LIMIT:
        return jsonify({"error": "All questions have been answered"}), 409
    if any(response.get("question") == question for response in responses):
        return jsonify({"error": "This question was already answered"}), 409
    try:
        slot = get_question_plan(interview, job, AI_INTERVIEW_QUESTION_LIMIT)[len(responses)]
    except (RuntimeError, IndexError) as exc:
        return jsonify({"error": "The interview plan is unavailable. Please reopen the interview."}), 503
    if question != slot["question"]:
        return jsonify({"error": "This question was already answered or is no longer current"}), 409
    if len(answer) > 50000:
        return jsonify({"error": "Answer must be under 50,000 characters"}), 400
    answer_html = None
    from app.services.interview_content_service import rich_answer, coding_answer_html
    if slot["type"] != "coding" and data.get("answer_format") == "html":
        answer, answer_html = rich_answer(answer)
        if not answer:
            return jsonify({"error": "Please type an answer before submitting"}), 400
    if slot["type"] == "coding":
        language = str(data.get("language") or "").strip()[:80]
        if not language:
            return jsonify({"error": "Choose a language for your code"}), 400
        explanation = str(data.get("explanation") or "").strip()[:10000]
        if data.get("explanation_format") == "html":
            explanation, explanation_html = rich_answer(explanation)
            answer_html = coding_answer_html(language, answer, explanation_html)
        answer = f"Language: {language}\nCode:\n{answer}\nExplanation and tests:\n{explanation}"

    # Commit the answer before contacting the AI provider. A provider failure must
    # never erase a submission or require the candidate to submit it twice.
    response_data = {
        "id": str(uuid.uuid4()),
        "interview_id": interview_id,
        "question": question,
        "answer": answer,
        "answer_html": answer_html,
        "score": None,
        "feedback": "Your answer is saved. AI feedback is pending; you can continue the interview.",
        "expected_answer": None,
        "evaluation_status": "pending",
    }
    saved = add_interview_response_once(response_data, len(responses))
    if not saved:
        return jsonify({"error": "This answer was already submitted. Reload to continue."}), 409
    try:
        response_data = evaluate_saved_response(job, interview_id, response_data)
        current_app.logger.info(f"Evaluation completed for response {response_data['id']}: score={response_data.get('score')}")
    except Exception as exc:
        current_app.logger.error(f"Evaluation failed for response {response_data['id']}: {str(exc)}", exc_info=True)
        response_data["feedback"] = f"Your answer is saved. AI feedback is temporarily unavailable due to a technical issue. You can continue the interview, and feedback will be available in your application details."
    return jsonify({
        "response_id": response_data["id"],
        "score": response_data["score"],
        "feedback": response_data["feedback"],
        "expected_answer": response_data["expected_answer"],
        "evaluation_status": response_data["evaluation_status"],
    })


@jobs_bp.route('/<string:job_id>/interviews/<string:interview_id>/finish', methods=['POST'])
def job_interview_finish(job_id, interview_id):
    job = get_job_by_id(job_id)
    if isinstance(job, tuple):
        return jsonify({"error": job[0].get('error', 'Job not found')}), 404

    active = session.get("active_interview") or {}
    if active.get("id") != interview_id or active.get("job_id") != job_id:
        return jsonify({"error": "Please start this interview in this browser first"}), 403

    interview = get_interview_by_id(interview_id)
    if not interview:
        return jsonify({"error": "Interview not found"}), 404

    responses = get_interview_responses(interview_id)
    if len(responses) < AI_INTERVIEW_QUESTION_LIMIT:
        return jsonify({"error": "Answer all interview questions before finishing"}), 400

    summary = interview_summary(responses)
    total_score, response_count, average_score = summary["total_score"], summary["responses"], summary["average_score"]

    complete_interview(interview_id)
    if interview.get("application_id"):
        update_application_status_and_score(
            interview.get("application_id"),
            "interview_completed",
            average_score,
        )

    return jsonify({
        "message": "Interview completed",
        "total_score": total_score,
        "average_score": average_score,
        "responses": response_count,
    })



@jobs_bp.get('/applications/<string:application_id>/resume')
def application_resume(application_id):
    application = get_application_by_id(application_id)
    if not application or not application.get('resume_path'):
        abort(404)
    candidate_access = str(session.get('candidate_id') or '') == str(application.get('user_id'))
    admin_access = bool(session.get('admin_id')) and session.get('admin_email') in current_app.config['ADMIN_EMAILS']
    job = get_job_by_id(application['job_id'])
    employer_access = not isinstance(job, tuple) and bool(session.get('employer_id')) and str(session['employer_id']) == str(job.get('employer_id'))
    if not (candidate_access or admin_access or employer_access):
        abort(404)
    path = find_application_resume(application['resume_path'], cv_directory())
    if not path:
        return render_template('shared/resume_unavailable.html', application=application,
                               is_candidate=candidate_access), 410
    response = send_from_directory(path.parent, path.name, as_attachment=path.suffix.lower() != '.pdf',
                                   download_name=application.get('resume_name') or path.name)
    response.headers['Cache-Control'] = 'private, no-store'
    return response


@jobs_bp.get('/categories')
def categories():
    groups = get_grouped_categories()
    counts = {}
    for job in get_all_jobs(hide_expired=True):
        key = str(job.get('category_id') or '')
        counts[key] = counts.get(key, 0) + 1
    return render_template('jobs/categories.html', groups=groups, counts=counts)


@jobs_bp.get('/job-match')
def job_match():
    if session.get('candidate_id'):
        return redirect(url_for('candidate_bp.resume_matches'))
    from app.blueprints.candidate_bp import resume_matches
    return resume_matches()
