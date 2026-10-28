from app.repository.job_repository import JobRepository
from app.services.job_content_service import clean_job_data


repo = JobRepository()


def get_jobs_by_employer_id(employer_id):
    return repo.fetch_by_employer_id(employer_id)


def get_job_by_id(job_id):
    row = repo.fetch_by_id(job_id)
    if not row:
        return {"error": "Job not found"}, 404
    return row


def create_job(data):
    required_fields = ["employer_id", "title", "category_id"]
    for field in required_fields:
        if not data.get(field):
            return {"error": f"{field} is required"}, 400

    job_id = repo.insert(clean_job_data(data))
    return {
        "message": "Job created",
        "id": job_id
    }


def update_job(job_id, data):
    required_fields = ["employer_id", "title", "category_id"]
    for field in required_fields:
        if not data.get(field):
            return {"error": f"{field} is required"}, 400

    updated = repo.update(job_id, clean_job_data(data))
    if not updated:
        return {"error": "Job not found"}, 404

    return {
        "message": "Job updated",
        "id": job_id
    }

def get_all_jobs(industry_id=None, category_id=None, experience_level=None, hide_expired=True):
    return repo.fetch_all(
        industry_id=industry_id,
        category_id=category_id,
        experience_level=experience_level,
        hide_expired=hide_expired,
    )
