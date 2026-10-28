import json
import unittest
from unittest.mock import patch

from app import app
from app.services.ai_interview_service import build_interview_plan, build_job_context
from app.services.interview_service import get_question_plan


QUESTIONS = [
    'Describe how you organized a project schedule when the deadline changed.',
    'Walk through a database migration that preserves existing records.',
    'How would you explain an unexpected outage to a customer?',
    'Implement a function that merges overlapping intervals; include boundary tests.',
    'What metrics would you use to measure the success of a new feature?',
    'Explain your strategy for resolving disagreements during a code review.',
    'Diagnose a process whose memory usage grows continuously.',
    'Design access controls for a shared document editing application.',
    'Write a query to calculate monthly active users, including empty months.',
    'How do you prioritize urgent requests from multiple stakeholders?',
    'Compare caching strategies for a frequently updated product catalogue.',
    'Demonstrate how you would investigate inconsistent financial totals.',
    'Build a rate limiter with deterministic tests and document its complexity.',
    'Outline a rollback procedure for a failed production deployment.',
    'Give an example of adapting your approach after receiving critical feedback.',
]
PLAN = [dict(question=q, type='coding' if i in (3, 8, 12) else 'question',
             focus=str(i), coverage=['Python']) for i, q in enumerate(QUESTIONS)]


class PlanTests(unittest.TestCase):
    def test_every_requirement_and_skill_allocated_and_technical_slots(self):
        job = dict(title='Engineer', description='\n'.join(f'Responsibility {i}' for i in range(24)),
                   skills=', '.join(f'Skill {i}' for i in range(12)), requirements='Accessible interfaces',
                   is_technical=True)
        with patch('app.services.ai_interview_service.call_ai', return_value=json.dumps(PLAN)):
            plan = build_interview_plan(job)
        coverage = [item for slot in plan for item in slot['coverage']]
        for i in range(24):
            self.assertIn(f'Responsibility {i}', coverage)
        for i in range(12):
            self.assertIn(f'Skill {i}', coverage)
        self.assertIn('Accessible interfaces', coverage)
        self.assertEqual([i for i, s in enumerate(plan) if s['type'] == 'coding'], [3, 8, 12])
        self.assertIn('Skill 11', build_job_context(job))

    def test_nontechnical_plan_has_no_coding(self):
        with patch('app.services.ai_interview_service.call_ai', return_value=json.dumps(PLAN)):
            plan = build_interview_plan(dict(title='Accountant'))
        self.assertTrue(all(s['type'] == 'question' for s in plan))

    def test_repeats_and_invalid_plans_are_repaired(self):
        for result in ('not JSON', '[]', json.dumps([{'question': QUESTIONS[0]}] * 15)):
            with self.subTest(result=result), patch('app.services.ai_interview_service.call_ai', return_value=result):
                plan = build_interview_plan(dict(title='Engineer', is_technical=True))
                self.assertEqual(len(plan), 15)
                self.assertEqual(len({slot['question'] for slot in plan}), 15)
                self.assertTrue(any(slot['source'] == 'prepared' for slot in plan))

    def test_prose_wrappers_and_truncated_arrays_keep_valid_questions(self):
        for raw in ("Here is the plan:\n" + json.dumps(PLAN) + "\nGood luck!",
                    json.dumps(dict(questions=PLAN)),
                    json.dumps(PLAN[:2])[:-1] + ', {"question": "unfinished'):
            with self.subTest(raw=raw[:30]), patch('app.services.ai_interview_service.call_ai', return_value=raw):
                plan = build_interview_plan(dict(title="Engineer"))
                self.assertEqual(plan[0]["question"], QUESTIONS[0])
                self.assertEqual(len(plan), 15)

    def test_provider_outage_still_produces_complete_technical_plan(self):
        with patch('app.services.ai_interview_service.call_ai', side_effect=RuntimeError("Unavailable")):
            plan = build_interview_plan(dict(title="Engineer", is_technical=True, requirements="Python"))
        self.assertEqual(len(plan), 15)
        for index in (3, 8, 12):
            self.assertEqual(plan[index]["type"], "coding")
            self.assertIn("Example:", plan[index]["question"])
            self.assertIn("Constraints:", plan[index]["question"])
            self.assertIn("Python", plan[index]["question"])

    def test_start_endpoint_saves_recovered_plan_and_reuses_it(self):
        app.config.update(TESTING=True, SECRET_KEY="test")
        client = app.test_client()
        with client.session_transaction() as session:
            session["candidate_id"] = "candidate"
        stored = dict(id="interview", status="in_progress", question_plan=None)
        from app.services import interview_service
        def save_plan(ident, plan):
            stored["question_plan"] = json.dumps(plan)
        with patch("app.blueprints.jobs_bp.get_job_by_id", return_value=dict(id="job", title="Engineer", ai_enabled=True, is_technical=True)), patch(
                "app.blueprints.jobs_bp.get_candidate_by_email", return_value=dict(id="candidate")), patch(
                "app.blueprints.jobs_bp.get_application_by_candidate_and_job", return_value=dict(id="application", status="interview_in_progress")), patch(
                "app.blueprints.jobs_bp.get_interview_by_application_id", return_value=stored), patch(
                "app.blueprints.jobs_bp.get_interview_responses", return_value=[]), patch.object(
                interview_service.repo, "fetch_responses_by_interview_id", return_value=[]), patch.object(
                interview_service.repo, "save_plan", side_effect=save_plan), patch.object(
                interview_service.repo, "fetch_by_id", return_value=stored), patch(
                "app.services.ai_interview_service.call_ai", return_value="Invalid provider response") as ai:
            result = client.post("/job/interview/start", json={"email": "candidate@example.invalid"})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json["question_number"], 1)
            self.assertEqual(len(json.loads(stored["question_plan"])), 15)
            again = client.post("/job/interview/start", json={"email": "candidate@example.invalid"})
            self.assertEqual(again.json["question"], result.json["question"])
            ai.assert_called_once()

    def test_saved_plan_is_reused_without_ai(self):
        with patch('app.services.ai_interview_service.call_ai') as ai:
            self.assertEqual(get_question_plan(dict(question_plan=json.dumps(PLAN)), {}), PLAN)
            ai.assert_not_called()


class InterviewFlowTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, SECRET_KEY='test')
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session['active_interview'] = dict(id='interview', job_id='job')
        self.responses = []
        self.interview = dict(id='interview', status='in_progress', total_score=0, response_count=0)
        patches = [
            patch('app.blueprints.jobs_bp.get_job_by_id', return_value=dict(id='job', ai_enabled=True)),
            patch('app.blueprints.jobs_bp.get_interview_by_id', return_value=self.interview),
            patch('app.blueprints.jobs_bp.get_interview_responses', side_effect=lambda _: self.responses),
            patch('app.blueprints.jobs_bp.get_question_plan', return_value=PLAN),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def post(self, action, **data):
        return self.client.post('/job/interviews/interview/' + action, json=data)

    def test_refresh_returns_same_slot_and_answer_advances(self):
        first = self.post('question').json
        self.assertEqual(first, self.post('question').json)
        def save(data, expected):
            self.assertEqual(expected, len(self.responses))
            self.responses.append(data)
            return True
        with patch('app.blueprints.jobs_bp.evaluate_saved_response', side_effect=lambda job, ident, response: dict(response, score=8, feedback='Good', expected_answer='A strong model answer', evaluation_status='completed')), patch(
                'app.blueprints.jobs_bp.add_interview_response_once', side_effect=save):
            self.assertEqual(self.post('answer', question=first['question'], answer='My answer').status_code, 200)
            self.assertEqual(self.post('answer', question=first['question'], answer='Retry').status_code, 409)
        second = self.post('question').json
        self.assertEqual(second['question_number'], 2)
        self.assertNotEqual(first['question'], second['question'])

    def test_finish_requires_all_questions(self):
        self.responses.append({})
        self.assertEqual(self.post('finish').status_code, 400)

    def test_cross_job_and_unknown_questions_rejected(self):
        self.assertEqual(self.client.post('/other/interviews/interview/question').status_code, 403)
        self.assertEqual(self.post('answer', question='Invented', answer='Answer').status_code, 409)

    def test_code_language_required_and_code_stored_for_review(self):
        self.responses.extend([{}] * 3)
        self.assertEqual(self.post('answer', question=QUESTIONS[3], answer='def solve(): pass').status_code, 400)
        with patch('app.blueprints.jobs_bp.evaluate_saved_response', side_effect=lambda job, ident, response: dict(response, score=7, feedback='Good', expected_answer='A strong model answer', evaluation_status='completed')), patch(
                'app.blueprints.jobs_bp.add_interview_response_once', return_value=True) as save:
            solution = '    def solve():\n        return []\n'
            result = self.post('answer', question=QUESTIONS[3], answer=solution,
                               language='Python', explanation='Test empty input')
        self.assertEqual(result.status_code, 200)
        self.assertIn('Language: Python', save.call_args.args[0]['answer'])
        self.assertIn('Test empty input', save.call_args.args[0]['answer'])
        self.assertIn('Code:\n' + solution + '\nExplanation', save.call_args.args[0]['answer'])

    def test_rich_written_answer_saved_safely_and_evaluated_as_text(self):
        with patch('app.blueprints.jobs_bp.evaluate_saved_response', side_effect=lambda job, ident, response: dict(response, score=8, feedback='Good', expected_answer='Example', evaluation_status='completed')), patch(
                'app.blueprints.jobs_bp.add_interview_response_once', return_value=True) as save:
            result = self.post('answer', question=QUESTIONS[0], answer='<p>Plan <strong>carefully</strong>.</p><ul><li>Review milestones</li></ul><script>bad()</script>', answer_format='html')
        self.assertEqual(result.status_code, 200)
        response = save.call_args.args[0]
        self.assertIn('Plan carefully.', response['answer'])
        self.assertIn('• Review milestones', response['answer'])
        self.assertNotIn('<strong>', response['answer'])
        self.assertIn('<strong>carefully</strong>', response['answer_html'])
        self.assertNotIn('<script>', response['answer_html'])
        self.assertNotIn('bad()', response['answer'])

    def test_visually_empty_rich_answers_are_rejected(self):
        for answer in ['<p><br></p>', '<p>&nbsp;</p>', '<script>bad()</script>', '<img src=x onerror=bad()>']:
            with self.subTest(answer=answer), patch('app.blueprints.jobs_bp.add_interview_response_once') as save:
                self.assertEqual(self.post('answer', question=QUESTIONS[0], answer=answer, answer_format='html').status_code, 400)
                save.assert_not_called()

    def test_coding_explanation_keeps_formatting_without_interpreting_code_as_html(self):
        self.responses.extend([{}] * 3)
        code = '    value = "<script>literal</script>"\n'
        with patch('app.blueprints.jobs_bp.evaluate_saved_response', side_effect=lambda job, ident, response: dict(response, score=8, feedback='Good', expected_answer='Example', evaluation_status='completed')), patch(
                'app.blueprints.jobs_bp.add_interview_response_once', return_value=True) as save:
            result = self.post('answer', question=QUESTIONS[3], answer=code, language='Python', explanation='<p><strong>O(n)</strong> time.</p>', explanation_format='html')
        self.assertEqual(result.status_code, 200)
        response = save.call_args.args[0]
        self.assertIn(code, response['answer'])
        self.assertIn('O(n) time.', response['answer'])
        self.assertIn('&lt;script&gt;literal&lt;/script&gt;', response['answer_html'])
        self.assertIn('<strong>O(n)</strong>', response['answer_html'])
        self.assertNotIn('<script>', response['answer_html'])

    def test_concurrent_duplicate_is_rejected_by_atomic_save(self):
        with patch('app.blueprints.jobs_bp.evaluate_saved_response', side_effect=lambda job, ident, response: dict(response, score=7, feedback='Good', expected_answer='A strong model answer', evaluation_status='completed')), patch(
                'app.blueprints.jobs_bp.add_interview_response_once', return_value=False):
            self.assertEqual(self.post('answer', question=QUESTIONS[0], answer='Answer').status_code, 409)


    def test_failed_evaluation_keeps_answer_saved_and_advances(self):
        def save(data, expected):
            self.responses.append(data)
            return True
        with patch('app.blueprints.jobs_bp.evaluate_saved_response', side_effect=RuntimeError('Malformed AI output')), patch(
                'app.blueprints.jobs_bp.add_interview_response_once', side_effect=save):
            result = self.post('answer', question=QUESTIONS[0], answer='My original answer')
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json['evaluation_status'], 'pending')
            self.assertIsNone(result.json['score'])
            self.assertEqual(self.responses[0]['answer'], 'My original answer')
            self.assertIsNone(self.responses[0]['score'])
            self.assertEqual(self.post('answer', question=QUESTIONS[0], answer='Retry').status_code, 409)
            self.assertEqual(self.post('question').json['question_number'], 2)

    def test_pending_evaluation_is_not_a_zero_grade(self):
        from app.services.interview_service import interview_summary
        result = interview_summary([dict(score=8), dict(score=None)])
        self.assertIsNone(result['average_score'])
        self.assertEqual(result['pending_evaluations'], 1)

    def test_finish_with_pending_feedback_preserves_ungraded_status(self):
        self.responses.extend([dict(score=None)] * 15)
        with patch('app.blueprints.jobs_bp.complete_interview'):
            result = self.post('finish')
        self.assertEqual(result.status_code, 200)
        self.assertIsNone(result.json['average_score'])
        self.assertEqual(result.json['responses'], 15)
