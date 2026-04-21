from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify

from app.services.job_service import get_all_jobs, get_job_by_id
from app.services.candidate_service import get_candidate_by_email, get_or_create_candidate
from app.services.application_service import (
    get_application_by_candidate_and_job,
    get_applications_by_job_id,
    submit_application,
    update_application_status,
    update_application_status_and_score,
)
from app.services.ai_interview_service import call_ai, generate_question, evaluate_answer, extract_score
from app.services.interview_service import (
    add_interview_response,
    complete_interview,
    create_interview,
    get_interview_by_application_id,
    get_interview_by_id,
    get_interview_responses,
)

jobs_bp = Blueprint('jobs_bp', __name__)
AI_INTERVIEW_QUESTION_LIMIT = 5


@jobs_bp.route('/')
def index():
    jobs = get_all_jobs()
    return render_template('jobs/jobs.html', jobs=jobs)


@jobs_bp.route('/<string:job_id>')
def job_detail(job_id):
    job = get_job_by_id(job_id)
    if isinstance(job, tuple):
        return render_template('jobs/job_detail.html', error=job[0].get('error', 'Job not found'))

    applications = get_applications_by_job_id(job_id)
    return render_template('jobs/job_detail.html', job=job, applications=applications)


@jobs_bp.route('/<string:job_id>/apply', methods=['GET', 'POST'])
def job_apply(job_id):
    job = get_job_by_id(job_id)
    if isinstance(job, tuple):
        return render_template('jobs/job_apply.html', error=job[0].get('error', 'Job not found'))

    if request.method == 'GET':
        return render_template('jobs/job_apply.html', job=job)

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

    application_result = submit_application({
        "job_id": job_id,
        "user_id": candidate["id"],
        "status": "submitted",
        "score": 0,
    })

    if isinstance(application_result, tuple):
        return render_template('jobs/job_apply.html', job=job, error=application_result[0].get('error', 'Failed to submit application'))

    flash("Application submitted successfully", "success")
    return redirect(url_for('jobs_bp.job_detail', job_id=job_id))


@jobs_bp.route('/<string:job_id>/easy-apply', methods=['GET', 'POST'])
def job_easy_apply(job_id):
    job = get_job_by_id(job_id)
    if isinstance(job, tuple):
        return render_template('jobs/job_easy_apply.html', error=job[0].get('error', 'Job not found'))

    if request.method == 'GET':
        return render_template('jobs/job_easy_apply.html', job=job)

    email = request.form.get("email", "").strip().lower()
    if not email:
        return render_template('jobs/job_easy_apply.html', job=job, error="Email is required")

    candidate = get_candidate_by_email(email)
    if not candidate:
        return render_template(
            'jobs/job_easy_apply.html',
            job=job,
            error="No candidate account found for that email. Please use manual apply or create a candidate account first."
        )

    application_result = submit_application({
        "job_id": job_id,
        "user_id": candidate["id"],
        "status": "submitted",
        "score": 0,
    })

    if isinstance(application_result, tuple):
        return render_template(
            'jobs/job_easy_apply.html',
            job=job,
            error=application_result[0].get('error', 'Failed to submit application')
        )

    flash("Easy application submitted successfully", "success")
    return redirect(url_for('jobs_bp.job_detail', job_id=job_id))


@jobs_bp.route('/<string:job_id>/interview', methods=['GET'])
def job_interview(job_id):
    job = get_job_by_id(job_id)
    if isinstance(job, tuple):
        return render_template('jobs/job_interview.html', error=job[0].get('error', 'Job not found'))

    return render_template('jobs/job_interview.html', job=job)


@jobs_bp.route('/<string:job_id>/interview/start', methods=['POST'])
def job_interview_start(job_id):
    job = get_job_by_id(job_id)
    if isinstance(job, tuple):
        return jsonify({"error": job[0].get('error', 'Job not found')}), 404

    if not job.get("ai_enabled"):
        return jsonify({"error": "AI interview is not enabled for this job"}), 400

    data = request.get_json(silent=True) or request.form
    email = (data.get("email") or "").strip().lower()
    if not email:
        return jsonify({"error": "Email is required"}), 400

    candidate = get_candidate_by_email(email)
    if not candidate:
        return jsonify({"error": "No candidate account found for that email"}), 404

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

    responses = get_interview_responses(interview["id"])
    if len(responses) >= AI_INTERVIEW_QUESTION_LIMIT:
        total_score = float(interview.get("total_score") or 0)
        response_count = int(interview.get("response_count") or len(responses))
        average_score = round(total_score / response_count, 2) if response_count else 0
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

    previous_questions = [response.get("question") for response in responses if response.get("question")]
    try:
        question = call_ai(generate_question(job.get("title"), previous_questions), max_tokens=120)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503

    return jsonify({
        "interview_id": interview["id"],
        "question": question,
        "question_number": len(responses) + 1,
        "question_limit": AI_INTERVIEW_QUESTION_LIMIT,
    })


@jobs_bp.route('/<string:job_id>/interviews/<string:interview_id>/question', methods=['POST'])
def job_interview_question(job_id, interview_id):
    job = get_job_by_id(job_id)
    if isinstance(job, tuple):
        return jsonify({"error": job[0].get('error', 'Job not found')}), 404

    interview = get_interview_by_id(interview_id)
    if not interview:
        return jsonify({"error": "Interview not found"}), 404

    if interview.get("status") == "completed":
        return jsonify({"error": "Interview already completed"}), 400

    responses = get_interview_responses(interview_id)
    if len(responses) >= AI_INTERVIEW_QUESTION_LIMIT:
        total_score = float(interview.get("total_score") or 0)
        response_count = int(interview.get("response_count") or len(responses))
        average_score = round(total_score / response_count, 2) if response_count else 0
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

    previous_questions = [response.get("question") for response in responses if response.get("question")]
    try:
        question = call_ai(generate_question(interview.get("role"), previous_questions), max_tokens=120)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503

    return jsonify({
        "question": question,
        "question_number": len(responses) + 1,
        "question_limit": AI_INTERVIEW_QUESTION_LIMIT,
    })


@jobs_bp.route('/<string:job_id>/interviews/<string:interview_id>/answer', methods=['POST'])
def job_interview_answer(job_id, interview_id):
    job = get_job_by_id(job_id)
    if isinstance(job, tuple):
        return jsonify({"error": job[0].get('error', 'Job not found')}), 404

    interview = get_interview_by_id(interview_id)
    if not interview:
        return jsonify({"error": "Interview not found"}), 404

    if interview.get("status") == "completed":
        return jsonify({"error": "Interview already completed"}), 400

    data = request.get_json(silent=True) or request.form
    question = (data.get("question") or "").strip()
    answer = (data.get("answer") or "").strip()

    if not question or not answer:
        return jsonify({"error": "Question and answer are required"}), 400

    evaluation_prompt = evaluate_answer(interview.get("role"), question, answer)
    try:
        ai_result = call_ai(evaluation_prompt, max_tokens=200)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503
    score = extract_score(ai_result)

    add_interview_response({
        "interview_id": interview_id,
        "question": question,
        "answer": answer,
        "score": score,
        "feedback": ai_result,
    })

    return jsonify({
        "score": score,
        "feedback": ai_result,
    })


@jobs_bp.route('/<string:job_id>/interviews/<string:interview_id>/finish', methods=['POST'])
def job_interview_finish(job_id, interview_id):
    job = get_job_by_id(job_id)
    if isinstance(job, tuple):
        return jsonify({"error": job[0].get('error', 'Job not found')}), 404

    interview = get_interview_by_id(interview_id)
    if not interview:
        return jsonify({"error": "Interview not found"}), 404

    responses = get_interview_responses(interview_id)
    if not responses:
        return jsonify({"error": "No interview responses found"}), 400

    total_score = float(interview.get("total_score") or 0)
    response_count = int(interview.get("response_count") or len(responses))
    average_score = round(total_score / response_count, 2) if response_count else 0

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
