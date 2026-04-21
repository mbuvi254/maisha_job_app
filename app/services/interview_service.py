from app.repository.interview_repository import InterviewRepository

repo = InterviewRepository()


def create_interview(data):
    interview_id = repo.insert(data)
    return repo.fetch_by_id(interview_id)


def get_interview_by_id(interview_id):
    return repo.fetch_by_id(interview_id)


def get_interview_by_application_id(application_id):
    return repo.fetch_by_application_id(application_id)


def get_interview_responses(interview_id):
    return repo.fetch_responses_by_interview_id(interview_id)


def add_interview_response(data):
    response_id = repo.insert_response(data)
    repo.update_totals(data.get("interview_id"), data.get("score", 0))
    return response_id


def complete_interview(interview_id):
    repo.mark_completed(interview_id)
