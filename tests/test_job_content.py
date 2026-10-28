from datetime import datetime, timedelta
import unittest
from unittest.mock import patch

from app import app
from app.services.ai_interview_service import build_job_context


class EmployerJobContentTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, SECRET_KEY='test')
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session['employer_id'] = 'employer'
        self.content = dict(
            title='Engineer', category_id='category', industry_id='industry',
            description='Role overview', responsibilities='Build services\nReview code',
            requirements='Python and SQL', who_should_apply='Engineers interested in mentoring',
            salary_insight='KES 100,000 per month', location='Nairobi · Hybrid',
            experience_level='Senior', deadline='2030-12-01T17:00',
        )
        self.job = dict(self.content, id='job', employer_id='employer',
                        created_at=datetime(2025, 1, 12), deadline=datetime.now() + timedelta(days=30))
        for p in [
            patch('app.blueprints.employer_bp.get_employer_by_id', return_value={'id': 'employer'}),
            patch('app.blueprints.employer_bp.get_job_by_id', return_value=self.job),
            patch('app.blueprints.employer_bp.get_industries', return_value=[]),
            patch('app.blueprints.employer_bp.get_grouped_categories', return_value=[]),
            patch('app.blueprints.employer_bp.get_category_by_id', return_value={'id': 'category', 'industry_id': 'industry'}),
        ]:
            p.start()
            self.addCleanup(p.stop)

    def test_create_and_edit_pass_structured_fields_to_storage(self):
        for path, service in [('/employers/jobs/new', 'create_job'),
                              ('/employers/jobs/job/edit', 'update_job')]:
            with self.subTest(path=path), patch('app.blueprints.employer_bp.' + service, return_value={'id': 'job'}) as save:
                response = self.client.post(path, data=dict(self.content, created_at='2000-01-01'))
                self.assertEqual(response.status_code, 302)
                saved = save.call_args.args[-1]
                for field in ('description', 'responsibilities', 'requirements', 'who_should_apply', 'salary_insight', 'location'):
                    self.assertEqual(saved[field], self.content[field])
                self.assertNotIn('created_at', saved)
                self.assertEqual(saved['deadline'], datetime(2030, 12, 1, 17))

    def test_form_preserves_new_fields_on_edit_and_validation_failure(self):
        response = self.client.get('/employers/jobs/job/edit')
        self.assertEqual(response.status_code, 200)
        for value in ('Build services\nReview code', 'Python and SQL', 'Nairobi · Hybrid', '12 Jan 2025'):
            self.assertIn(value.encode(), response.data)
        with patch('app.blueprints.employer_bp.get_category_by_id', return_value=None):
            response = self.client.post('/employers/jobs/job/edit', data=dict(self.content, requirements='Changed requirement', deadline=''))
        self.assertIn(b'Changed requirement', response.data)
        self.assertIn(b'value=""', response.data)
        self.assertIn(b'Category is required', response.data)

    def test_employer_preview_and_interview_context_include_sections(self):
        response = self.client.get('/employers/jobs/job')
        self.assertEqual(response.status_code, 200)
        for value in ('Overview', 'What you will do', 'Requirements', 'Who should apply',
                      'Salary insight', 'Nairobi · Hybrid', '12 Jan 2025'):
            self.assertIn(value.encode(), response.data)
        context = build_job_context(self.job)
        for field in ('description', 'responsibilities', 'requirements', 'who_should_apply'):
            self.assertIn(self.job[field], context)
