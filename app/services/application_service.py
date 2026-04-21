from app.repository.application_repository import ApplicationRepository


repo = ApplicationRepository()


def get_applications_by_job_id(job_id):
    return repo.fetch_by_job_id(job_id)


def get_application_by_id(application_id):
    return repo.fetch_by_id(application_id)


def get_application_by_candidate_and_job(candidate_id, job_id):
    return repo.fetch_by_candidate_and_job(candidate_id, job_id)


def get_all_applications_for_employer_jobs(job_ids):
    if not job_ids:
        return []

    applications = []
    for job_id in job_ids:
        applications.extend(repo.fetch_by_job_id(job_id))

    return applications


def submit_application(data):
    required_fields = ["job_id", "user_id"]
    for field in required_fields:
        if not data.get(field):
            return {"error": f"{field} is required"}, 400

    existing = repo.fetch_by_candidate_and_job(data.get("user_id"), data.get("job_id"))
    if existing:
        return {"error": "You have already applied for this job"}, 400

    application_id = repo.insert(data)
    return {
        "message": "Application submitted",
        "id": application_id
    }


def update_application_status(application_id, status):
    return repo.update_status(application_id, status)


def update_application_score(application_id, score):
    return repo.update_score(application_id, score)


def update_application_status_and_score(application_id, status, score):
    return repo.update_status_and_score(application_id, status, score)
