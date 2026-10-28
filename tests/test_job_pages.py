from datetime import datetime, timedelta
import unittest
from unittest.mock import patch

from app import app


def sample_job(number=1):
    return dict(id=f'job-{number}', title=f'Software Engineer {number}', description='Build useful products.\nCollaborate with the team.', skills='Python, Flask, SQL, Git, Testing', industry_name='Technology', category_name='Software Engineering', category_id='software', experience_level='Senior', resume_required=True, ai_enabled=True, created_at=datetime.now(), deadline=datetime.now()+timedelta(days=30))


class JobPageTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, SECRET_KEY='test-secret')
        self.client=app.test_client()
        self.jobs=[sample_job(n) for n in range(1,26)]
        self.patches=[patch('app.blueprints.jobs_bp.get_all_jobs',return_value=self.jobs),patch('app.blueprints.jobs_bp.get_industries',return_value=[]),patch('app.blueprints.jobs_bp.get_grouped_categories',return_value=[]),patch('app.blueprints.jobs_bp.get_job_by_id',return_value=self.jobs[0])]
        for p in self.patches:p.start()
        self.addCleanup(lambda:[p.stop() for p in reversed(self.patches)])

    def test_listing_paginates_and_preserves_search(self):
        response=self.client.get('/jobs?q=software&page=2')
        self.assertEqual(response.status_code,200)
        self.assertIn(b'Software Engineer 21',response.data)
        self.assertNotIn(b'>Software Engineer 1</a>',response.data)
        self.assertIn(b'q=software',response.data)
        self.assertIn(b'Page 2 of 2',response.data)

    def test_invalid_page_and_empty_results(self):
        for page in ['invalid','-2','999']:
            self.assertEqual(self.client.get('/jobs?page='+page).status_code,200)
        response=self.client.get('/jobs?q=unmatched')
        self.assertIn(b'No matching opportunities yet',response.data)
        self.assertIn(b'<strong>0</strong> of <strong>0</strong>',response.data)

    def test_detail_and_legacy_url_both_work(self):
        for url in ['/jobs/job-1','/job-1']:
            response=self.client.get(url)
            self.assertEqual(response.status_code,200)
            self.assertIn(b'Overview',response.data)
            self.assertIn(b'Complete your AI interview',response.data)
            self.assertIn(b'/job-1/apply',response.data)
            self.assertIn(b'Sign in for easy apply',response.data)

    def test_detail_description_is_escaped_and_preserves_lines(self):
        self.jobs[0]['description']='<script>alert(1)</script>\nSecond paragraph'
        response=self.client.get('/jobs/job-1')
        self.assertNotIn(b'<script>alert(1)</script>',response.data)
        self.assertIn(b'&lt;script&gt;alert(1)&lt;/script&gt;\nSecond paragraph',response.data)

    def test_applied_candidate_sees_status_instead_of_apply(self):
        with self.client.session_transaction() as session:session['candidate_id']='candidate-1'
        with patch('app.blueprints.jobs_bp.get_candidate_by_id',return_value={'id':'candidate-1'}),patch('app.blueprints.jobs_bp.get_application_by_candidate_and_job',return_value={'id':'application-1'}),patch('app.blueprints.jobs_bp.get_saved_job_by_candidate_and_job',return_value=None):
            response=self.client.get('/jobs/job-1')
        self.assertIn(b'Application submitted',response.data)
        self.assertNotIn(b'>Apply now</a>',response.data)

    def test_saved_candidate_can_unsave_and_easy_apply(self):
        with self.client.session_transaction() as session:session['candidate_id']='candidate-1'
        with patch('app.blueprints.jobs_bp.get_candidate_by_id',return_value={'id':'candidate-1'}),patch('app.blueprints.jobs_bp.get_application_by_candidate_and_job',return_value=None),patch('app.blueprints.jobs_bp.get_saved_job_by_candidate_and_job',return_value={'id':'saved-1'}):
            response=self.client.get('/jobs/job-1')
        self.assertIn(b'/job-1/easy-apply',response.data)
        self.assertIn(b'bi-bookmark-check-fill',response.data)
        self.assertIn(b'/job-1/save',response.data)

    def test_unavailable_and_optional_fields(self):
        self.jobs[0].update(ai_enabled=False,description=None,skills=None,created_at=None,deadline=None)
        response=self.client.get('/jobs/job-1')
        self.assertEqual(response.status_code,200)
        self.assertNotIn(b'Complete your AI interview',response.data)
        self.assertIn(b'No deadline published',response.data)
        with patch('app.blueprints.jobs_bp.get_job_by_id',return_value=({'error':'Job not found'},404)):
            response=self.client.get('/jobs/missing')
        self.assertIn(b'This opportunity is unavailable',response.data)
        self.assertNotIn(b'>Apply now</a>',response.data)

    def test_structured_job_sections_and_metadata(self):
        self.jobs[0].update(responsibilities='Build APIs.\nReview code.',
                            requirements='Three years of Python.',
                            who_should_apply='Engineers who enjoy mentoring.',
                            salary_insight='KES 100,000–150,000 per month.',
                            location='Nairobi · Hybrid')
        response = self.client.get('/jobs/job-1')
        for heading in ('Overview', 'What you will do', 'Requirements', 'Who should apply',
                        'Salary insight', 'Location', 'Posted date', 'Deadline'):
            self.assertIn(heading.encode(), response.data)
        for field in ('description', 'responsibilities', 'requirements', 'who_should_apply',
                      'salary_insight', 'location'):
            self.assertIn(self.jobs[0][field].encode(), response.data)

    def test_missing_sections_and_untrusted_content(self):
        for field in ('responsibilities', 'requirements', 'who_should_apply', 'salary_insight', 'location'):
            self.jobs[0][field] = '<script>alert(1)</script>'
        response = self.client.get('/jobs/job-1')
        self.assertNotIn(b'<script>alert(1)</script>', response.data)
        self.assertIn(b'&lt;script&gt;alert(1)&lt;/script&gt;', response.data)
        for field in ('responsibilities', 'requirements', 'who_should_apply', 'salary_insight', 'location'):
            self.jobs[0][field] = None
        response = self.client.get('/jobs/job-1')
        self.assertIn(b'Salary information has not been disclosed', response.data)
        self.assertIn(b'Not specified', response.data)
