from app.repository.candidate_repository import CandidateRepository


repo = CandidateRepository()


def get_candidate_by_email(email):
    row = repo.fetch_by_email(email)
    if not row:
        return None
    return row


def get_candidate_by_id(candidate_id):
    row = repo.fetch_by_id(candidate_id)
    if not row:
        return None
    return row


def get_or_create_candidate(data):
    existing = repo.fetch_by_email(data.get("email"))
    if existing:
        return existing

    candidate_id = repo.insert(data)
    return repo.fetch_by_id(candidate_id)
