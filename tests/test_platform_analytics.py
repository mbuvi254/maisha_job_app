import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import app
from test_candidate_cv import cv_docx
from app.services.site_activity_service import guest_resume, claim_guest, activity_summary, connect


class PlatformAnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = dict(app.config)
        self.addCleanup(lambda: app.config.update(self.settings))
        app.config.update(TESTING=True, SECRET_KEY='test', ADMIN_EMAILS=['admin@example.invalid'],
                          ACTIVITY_DATABASE=str(Path(self.temp.name) / 'activity.sqlite3'))
        self.client = app.test_client()
        self.cv_patch = patch('app.services.candidate_resume_service.cv_directory', return_value=Path(self.temp.name))
        self.cv_patch.start()
        self.addCleanup(self.cv_patch.stop)
        self.job = dict(id='python', title='Python Engineer', skills='Python, SQL, Flask', description='API design development testing')
        with self.client.session_transaction() as session:
            session['auth_csrf'] = 'csrf'

    def upload(self):
        return self.client.post('/candidates/matches', data={'csrf_token': 'csrf', 'cv': (cv_docx(), 'resume.docx')})

    def test_guest_upload_private_storage_and_remembered_matches(self):
        self.assertEqual(self.upload().status_code, 302)
        with self.client.session_transaction() as session:
            token = session['guest_resume_token']
            self.assertNotIn('cv_text', session)
        with app.app_context():
            data = guest_resume(token)
            self.assertIn('Python developer', data['cv_text'])
            self.assertTrue((Path(self.temp.name) / data['cv_filename']).exists())
            self.assertIsNone(guest_resume('different-browser'))
        with patch('app.blueprints.candidate_bp.get_all_jobs', return_value=[self.job]):
            response = self.client.get('/candidates/matches')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Python Engineer', response.data)
        self.assertIn(b'WE REMEMBER YOUR RESUME', response.data)
        self.assertIn(b'overlap', response.data)

    def test_guest_upload_requires_csrf_and_rejects_invalid_file(self):
        self.assertEqual(self.client.post('/candidates/matches').status_code, 400)
        response = self.client.post('/candidates/matches', data={'csrf_token': 'csrf', 'cv': (cv_docx(), 'bad.exe')})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Upload a PDF or DOCX', response.data)

    def test_expired_guest_resume_cannot_be_read_or_claimed(self):
        self.upload()
        with self.client.session_transaction() as session:
            token = session['guest_resume_token']
        with app.app_context(), connect() as conn:
            conn.execute('UPDATE guest_resumes SET created_at=0')
        with app.app_context(), patch('app.services.candidate_service.update_candidate_cv') as update:
            self.assertIsNone(claim_guest(token, 'candidate'))
            update.assert_not_called()

    def test_claim_transfers_to_profile_and_cannot_be_reused(self):
        self.upload()
        with self.client.session_transaction() as session:
            token = session['guest_resume_token']
        with app.app_context(), patch('app.services.candidate_service.update_candidate_cv') as update:
            data = claim_guest(token, 'candidate')
            update.assert_called_once_with('candidate', data)
            self.assertIsNone(guest_resume(token))
            self.assertTrue((Path(self.temp.name) / data['cv_filename']).exists())

    def test_admin_endpoints_deny_guests_and_candidates(self):
        for path in ['/admin/analytics', '/admin/data/candidates', '/admin/resumes/candidate']:
            self.assertEqual(self.client.get(path).status_code, 403)
        with self.client.session_transaction() as session:
            session['candidate_id'] = 'candidate'
        self.assertEqual(self.client.get('/admin/analytics').status_code, 403)
        self.assertEqual(self.client.get('/admin/data/resumes').status_code, 403)

    def test_analytics_handles_empty_site_and_safe_directory_render(self):
        with self.client.session_transaction() as session:
            session['admin_id'] = 'admin'
            session['admin_email'] = 'admin@example.invalid'
        with patch('app.services.admin_service.get_growth', return_value=dict(days=[],series={},totals={})):
            response = self.client.get('/admin/analytics')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json['website']['totals']['requests'], 0)
        with patch('app.services.admin_service.get_directory', return_value=dict(kind='candidates', columns=['email'], rows=[{'email':'<script>bad()</script>'}],count=1,page=1,query='')):
            response = self.client.get('/admin/data/candidates')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b'<script>bad()</script>', response.data)
        self.assertEqual(self.client.get('/admin/data/not-a-table').status_code,404)

    def test_request_logging_omits_secrets_and_sessions_persist(self):
        app.config['TESTING'] = False
        with self.client.session_transaction() as session:
            session['candidate_id'] = 'candidate'
        response = self.client.get('/candidates/login?secret=do-not-record')
        self.assertIn('Expires=', response.headers.get('Set-Cookie', ''))
        with app.app_context():
            summary = activity_summary()
        self.assertEqual(summary['totals']['requests'], 1)
        self.assertEqual(summary['logs'][0]['path'], '/candidates/login')
        self.assertNotIn('do-not-record', str(summary))
        self.assertGreater(app.permanent_session_lifetime.days, 300)

    def test_persistent_matches_requires_authentication(self):
        self.assertEqual(self.client.get('/candidates/matches/preview').status_code,401)
        with self.client.session_transaction() as session:
            session['candidate_id'] = 'candidate'
        with patch('app.blueprints.candidate_bp.get_candidate_by_id', return_value={'id':'candidate','cv_text':'Python SQL Flask development testing'}), patch('app.blueprints.candidate_bp.get_all_jobs', return_value=[self.job]):
            response = self.client.get('/candidates/matches/preview')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Python Engineer',response.data)
