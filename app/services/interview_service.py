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


def get_question_plan(interview, job, limit=15):
    import json
    from app.services.ai_interview_service import build_interview_plan
    if not interview.get("question_plan"):
        previous = [r["question"] for r in repo.fetch_responses_by_interview_id(interview["id"])]
        # Legacy interviews retain their answered slots and receive new remaining questions.
        remaining = build_interview_plan(job, previous_questions=previous, limit=limit - len(previous))
        plan = [dict(question=q, type="question", focus="Previously answered", coverage=[]) for q in previous]
        plan.extend(remaining)
        repo.save_plan(interview["id"], plan)
        interview = repo.fetch_by_id(interview["id"])
    return json.loads(interview["question_plan"])


def add_interview_response_once(data, expected_count):
    return repo.insert_response_once(data, expected_count)


def evaluate_saved_response(job, interview_id, response):
    from app.services.ai_interview_service import call_ai, evaluate_answer, parse_evaluation, EVALUATION_RESPONSE_FORMAT
    try:
        # Try with structured JSON format first
        evaluation = parse_evaluation(call_ai(evaluate_answer(job, response["question"], response["answer"]), max_tokens=4000, response_format=EVALUATION_RESPONSE_FORMAT))
    except Exception as e:
        # If structured format fails, try without it
        from flask import current_app
        current_app.logger.warning(f"Structured evaluation failed, trying without response_format: {str(e)}")
        try:
            ai_response = call_ai(evaluate_answer(job, response["question"], response["answer"]), max_tokens=4000, response_format=None)
            evaluation = parse_evaluation(ai_response)
        except Exception as e2:
            current_app.logger.error(f"Both evaluation methods failed: {str(e2)}", exc_info=True)
            raise e2
    saved = repo.finish_evaluation(interview_id, response["id"], evaluation)
    interview = repo.fetch_by_id(interview_id)
    if interview.get("status") == "completed":
        responses = repo.fetch_responses_by_interview_id(interview_id)
        summary = interview_summary(responses)
        if interview.get("application_id"):
            from app.services.application_service import update_application_status_and_score
            update_application_status_and_score(interview["application_id"], "interview_completed", summary["average_score"])
    return saved


def interview_summary(responses):
    pending = sum(response.get("score") is None for response in responses)
    total = sum(float(response.get("score") or 0) for response in responses)
    return dict(total_score=total, responses=len(responses), pending_evaluations=pending,
                average_score=None if pending or not responses else round(total / len(responses), 2))
