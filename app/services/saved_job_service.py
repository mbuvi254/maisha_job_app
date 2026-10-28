from app.repository.saved_job_repository import SavedJobRepository


repo = SavedJobRepository()


def get_saved_job_by_candidate_and_job(candidate_id, job_id):
    return repo.fetch_by_candidate_and_job(candidate_id, job_id)


def get_saved_jobs_by_candidate_id(candidate_id):
    return repo.fetch_by_candidate_id(candidate_id)


def save_job_for_candidate(candidate_id, job_id):
    if not candidate_id or not job_id:
        return {"error": "candidate_id and job_id are required"}, 400

    existing = repo.fetch_by_candidate_and_job(candidate_id, job_id)
    if existing:
        return {"error": "Job already saved"}, 400

    saved_job_id = repo.insert(candidate_id, job_id)
    return {
        "message": "Job saved",
        "id": saved_job_id,
    }


def unsave_job_for_candidate(candidate_id, job_id):
    if not candidate_id or not job_id:
        return {"error": "candidate_id and job_id are required"}, 400

    deleted = repo.delete(candidate_id, job_id)
    if not deleted:
        return {"error": "Saved job not found"}, 404

    return {
        "message": "Job removed from saved jobs",
    }
