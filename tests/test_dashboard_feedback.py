from datetime import datetime
import json
import unittest
from unittest.mock import patch

from app import app
from app.services.ai_interview_service import parse_evaluation


class DashboardFeedbackTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, SECRET_KEY='test', ADMIN_EMAILS=['admin@example.invalid'])
        self.client = app.test_client()
        self.candidate = dict(id='candidate', first_name='Amina', email='candidate@example.invalid')
        self.job = dict(id='job', title='Software Engineer', ai_enabled=True, location='Nairobi', category_name='Engineering')
        self.application = dict(id='application', user_id='candidate', job_id='job',
                                status='interview_in_progress', created_at=datetime(2026, 10, 27))
        self.interview = dict(id='interview', status='in_progress', response_count=1, total_score=8)
        self.response = dict(question='Explain a database index.', answer='<script>bad()</script>',
                             feedback='Discuss write costs.', expected_answer='An index speeds reads with additional storage and write costs.', score=8)

    def sign_in_candidate(self):
        with self.client.session_transaction() as session:
            session['candidate_id'] = 'candidate'

    def test_candidate_progress_and_persisted_feedback(self):
        self.sign_in_candidate()
        with patch('app.blueprints.candidate_bp.get_candidate_by_id', return_value=self.candidate), patch(
                'app.blueprints.candidate_bp.get_applications_by_candidate_id', return_value=[self.application]), patch(
                'app.blueprints.candidate_bp.get_saved_jobs_by_candidate_id', return_value=[]), patch(
                'app.blueprints.candidate_bp.get_job_by_id', return_value=self.job), patch(
                'app.blueprints.candidate_bp.get_interview_by_application_id', return_value=self.interview):
            profile = self.client.get('/candidates/profile')
        self.assertEqual(profile.status_code, 200)
        for value in ('Software Engineer', '1 / 15 answered', 'Continue interview', 'View progress &amp; feedback'):
            self.assertIn(value.encode(), profile.data)
        with patch('app.blueprints.candidate_bp.get_candidate_by_id', return_value=self.candidate), patch(
                'app.blueprints.candidate_bp.get_application_by_id', return_value=self.application), patch(
                'app.blueprints.candidate_bp.get_job_by_id', return_value=self.job), patch(
                'app.blueprints.candidate_bp.get_interview_by_application_id', return_value=self.interview), patch(
                'app.blueprints.candidate_bp.get_interview_responses', return_value=[self.response]):
            review = self.client.get('/candidates/applications/application')
        self.assertEqual(review.status_code, 200)
        self.assertIn(self.response['expected_answer'].encode(), review.data)
        self.assertIn(b'Submitted answers are locked', review.data)
        self.assertNotIn(b'<script>bad()</script>', review.data)

    def test_candidate_cannot_read_another_application(self):
        self.sign_in_candidate()
        with patch('app.blueprints.candidate_bp.get_candidate_by_id', return_value=self.candidate), patch(
                'app.blueprints.candidate_bp.get_application_by_id', return_value=dict(self.application, user_id='someone-else')):
            self.assertEqual(self.client.get('/candidates/applications/application').status_code, 404)
        self.client = app.test_client()
        self.assertEqual(self.client.get('/candidates/applications/application').status_code, 302)

    def test_admin_metrics_and_recent_activity_render(self):
        with self.client.session_transaction() as session:
            session['admin_id'] = 'admin'
            session['admin_email'] = 'admin@example.invalid'
        activity = dict(totals=dict(candidates=12, applications=23, completed_interviews=4,
                                   active_interviews=3, answers=31, average_score=7.5),
                        statuses=[dict(status='submitted', count=10)],
                        recent=[dict(self.application, first_name='Amina', title='Engineer')])
        with patch('app.blueprints.auth_bp.get_all_employers', return_value=[]), patch(
                'app.services.job_service.get_all_jobs', return_value=[]), patch(
                'app.services.admin_service.get_platform_activity', return_value=activity):
            result = self.client.get('/admin/dashboard')
        self.assertEqual(result.status_code, 200)
        for value in ('Application pipeline', 'Recent applications', '31 answers reviewed', '7.5 / 10', 'Amina'):
            self.assertIn(value.encode(), result.data)

    def test_evaluation_requires_suggested_answer_and_valid_score(self):
        good = dict(score=8.5, feedback='Useful detail', expected_answer='An example response')
        self.assertEqual(parse_evaluation(json.dumps(good)), good)
        self.assertEqual(parse_evaluation('Here is the review:\n' + json.dumps(good) + '\nOther valid approaches exist.'), good)
        for bad in ({'score': 8, 'feedback': 'Missing model answer'}, dict(good, score=99),
                    dict(good, score=True), dict(good, expected_answer='')):
            with self.assertRaises(RuntimeError):
                parse_evaluation(json.dumps(bad))

    def test_email_alone_cannot_start_someone_elses_interview(self):
        with patch('app.blueprints.jobs_bp.get_job_by_id', return_value=self.job), patch(
                'app.blueprints.jobs_bp.get_candidate_by_email', return_value=self.candidate):
            result = self.client.post('/job/interview/start', json={'email': self.candidate['email']})
        self.assertEqual(result.status_code, 403)


    def test_pending_interview_actions_and_cv_matches(self):
        self.sign_in_candidate()
        candidate = dict(self.candidate, cv_text="Python and SQL developer", cv_filename="cv.pdf", cv_name="CV.pdf")
        completed = dict(self.application, id="finished", status="interview_completed")
        new_match = dict(self.job, id="other", title="Python Developer", skills="Python, SQL", description="Build APIs")
        with patch('app.blueprints.candidate_bp.get_candidate_by_id', return_value=candidate), patch(
                'app.blueprints.candidate_bp.get_applications_by_candidate_id', return_value=[self.application, completed]), patch(
                'app.blueprints.candidate_bp.get_saved_jobs_by_candidate_id', return_value=[]), patch(
                'app.blueprints.candidate_bp.get_job_by_id', return_value=self.job), patch(
                'app.blueprints.candidate_bp.get_interview_by_application_id', side_effect=[
                    self.interview, dict(self.interview, status="completed")]), patch(
                'app.blueprints.candidate_bp.get_all_jobs', return_value=[new_match]) as get_jobs:
            result = self.client.get('/candidates/profile')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data.count(b'class="pending-interview"'), 1)
        self.assertIn(b'start=1', result.data)
        self.assertIn(b'Python Developer', result.data)
        self.assertIn(b'Upload once', result.data)
        get_jobs.assert_called_once_with(hide_expired=True)

    def test_pending_feedback_renders_without_zero_grade_and_can_retry(self):
        self.sign_in_candidate()
        pending = dict(self.response, id='response', score=None, expected_answer=None, evaluation_status='pending')
        with patch('app.blueprints.candidate_bp.get_candidate_by_id', return_value=self.candidate), patch(
                'app.blueprints.candidate_bp.get_application_by_id', return_value=self.application), patch(
                'app.blueprints.candidate_bp.get_job_by_id', return_value=self.job), patch(
                'app.blueprints.candidate_bp.get_interview_by_application_id', return_value=self.interview), patch(
                'app.blueprints.candidate_bp.get_interview_responses', return_value=[pending]), patch(
                'app.blueprints.candidate_bp.evaluate_saved_response') as evaluate, patch(
                'app.blueprints.auth_bp.check_csrf'):
            result = self.client.get('/candidates/applications/application')
            self.assertEqual(result.status_code, 200)
            self.assertIn(b'Pending feedback', result.data)
            self.assertIn(b'Retry AI feedback', result.data)
            result = self.client.post('/candidates/applications/application/responses/response/retry-feedback')
        self.assertEqual(result.status_code, 302)
        evaluate.assert_called_once()
        self.assertEqual(evaluate.call_args.args[-1]['answer'], pending['answer'])

    def test_retry_cannot_access_other_candidates_answer(self):
        self.sign_in_candidate()
        with patch('app.blueprints.auth_bp.check_csrf'), patch(
                'app.blueprints.candidate_bp.get_application_by_id', return_value=dict(self.application, user_id='other')):
            self.assertEqual(self.client.post('/candidates/applications/application/responses/response/retry-feedback').status_code, 404)
