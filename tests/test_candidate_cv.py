import io
from pathlib import Path
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta
from unittest.mock import patch

from werkzeug.datastructures import FileStorage

from app import app
from app.services.candidate_resume_service import save_profile_cv, match_open_jobs


def cv_docx():
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w') as archive:
        archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Python developer with SQL database design, Flask API development and testing experience.</w:t></w:r></w:p></w:body></w:document>')
    data.seek(0)
    return data


class CvTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, SECRET_KEY='test')
        self.client = app.test_client()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.candidate = dict(id='candidate', email='candidate@example.invalid', first_name='Amina')
        self.job = dict(id='job', title='Backend Developer', ai_enabled=True, resume_required=True,
                        skills='Python, SQL, Flask', description='API development and testing',
                        deadline=datetime.now() + timedelta(days=10))
        with self.client.session_transaction() as session:
            session['candidate_id'] = 'candidate'
            session['auth_csrf'] = 'csrf'

    def test_valid_docx_is_saved_privately_and_bad_files_rejected(self):
        with app.app_context(), patch('app.services.candidate_resume_service.cv_directory', return_value=self.directory):
            data = save_profile_cv(FileStorage(cv_docx(), filename='My CV.docx'))
            self.assertIn('Python developer', data['cv_text'])
            self.assertTrue((self.directory / data['cv_filename']).is_file())
            self.assertNotIn('My', data['cv_filename'])
            for name, content in [('cv.exe', b'bad'), ('cv.pdf', b'not a PDF'), ('cv.docx', b'PK invalid')]:
                with self.subTest(name=name), self.assertRaises(ValueError):
                    save_profile_cv(FileStorage(io.BytesIO(content), filename=name))

    def test_match_ranking_and_already_applied_exclusion(self):
        accounting = dict(id='finance', title='Accountant', skills='Audit, Payroll', description='Prepare financial reports')
        matches = match_open_jobs('Python SQL Flask API developer testing', [accounting, self.job])
        self.assertEqual(matches[0]['job']['id'], 'job')
        self.assertIn('SQL', matches[0]['matched_skills'])
        self.assertEqual(match_open_jobs('Python SQL Flask API developer testing', [self.job], ['job']), [])
        self.assertEqual(match_open_jobs('', [self.job]), [])

    def test_upload_requires_authentication_and_csrf(self):
        client = app.test_client()
        self.assertEqual(client.post('/candidates/profile/cv').status_code, 302)
        self.assertEqual(self.client.post('/candidates/profile/cv').status_code, 400)

    def test_upload_persists_text_and_refreshes_matches(self):
        with patch('app.blueprints.candidate_bp.get_candidate_by_id', return_value=self.candidate), patch(
                'app.services.candidate_resume_service.cv_directory', return_value=self.directory), patch(
                'app.blueprints.candidate_bp.update_candidate_cv') as save, patch(
                'app.blueprints.auth_bp.check_csrf'):
            result = self.client.post('/candidates/profile/cv', data={'cv': (cv_docx(), 'My CV.docx')})
        self.assertEqual(result.status_code, 302)
        self.assertIn('#job-matches', result.location)
        self.assertEqual(save.call_args.args[0], 'candidate')
        self.assertIn('Python developer', save.call_args.args[1]['cv_text'])

    def test_private_cv_and_application_download_require_ownership(self):
        cv_path = self.directory / 'cv.docx'
        cv_path.write_bytes(cv_docx().getvalue())
        candidate = dict(self.candidate, cv_filename='cv.docx', cv_name='My CV.docx')
        with patch('app.blueprints.candidate_bp.get_candidate_by_id', return_value=candidate), patch(
                'app.blueprints.candidate_bp.cv_directory', return_value=self.directory):
            result = self.client.get('/candidates/profile/cv')
            self.assertEqual(result.status_code, 200)
            self.assertIn('no-store', result.headers['Cache-Control'])
            result.close()
        application = dict(id='application', job_id='job', user_id='someone-else', resume_path='candidate_cvs/cv.docx')
        with patch('app.blueprints.jobs_bp.get_application_by_id', return_value=application), patch(
                'app.blueprints.jobs_bp.get_job_by_id', return_value=self.job):
            self.assertEqual(self.client.get('/applications/application/resume').status_code, 404)
        self.assertEqual(app.test_client().get('/candidates/profile/cv').status_code, 401)

    def test_easy_apply_reuses_saved_cv(self):
        candidate = dict(self.candidate, cv_filename='cv.docx', cv_name='My CV.docx')
        (self.directory / 'cv.docx').write_bytes(cv_docx().getvalue())
        with patch('app.blueprints.jobs_bp.get_job_by_id', return_value=self.job), patch(
                'app.blueprints.jobs_bp.get_candidate_by_id', return_value=candidate), patch(
                'app.blueprints.jobs_bp.get_application_by_candidate_and_job', return_value=None), patch(
                'app.blueprints.jobs_bp.cv_directory', return_value=self.directory), patch(
                'app.blueprints.jobs_bp.analyze_resume_fit', return_value=None), patch(
                'app.blueprints.jobs_bp.submit_application', return_value={'id': 'new'}) as submit, patch(
                'app.blueprints.jobs_bp._send_application_and_interview_emails'):
            result = self.client.post('/job/easy-apply', data={'use_profile_cv': 'on'})
        self.assertEqual(result.status_code, 302)
        self.assertEqual(submit.call_args.args[0]['resume_path'], 'candidate_cvs/cv.docx')

    def test_expired_interview_and_missing_job_do_not_crash(self):
        expired = dict(self.job, deadline=datetime.now() - timedelta(days=1))
        with patch('app.blueprints.jobs_bp.get_job_by_id', return_value=expired), patch(
                'app.blueprints.jobs_bp.get_candidate_by_id', return_value=self.candidate):
            result = self.client.get('/job/interview?start=1')
        self.assertEqual(result.status_code, 200)
        self.assertIn(b'const autoStartInterview = true', result.data)
        with patch('app.blueprints.jobs_bp.get_job_by_id', return_value=({'error': 'Job not found'}, 404)):
            result = self.client.get('/job/interview')
        self.assertEqual(result.status_code, 200)
        self.assertIn(b'Job not found', result.data)
        self.assertNotIn(b'const startUrl', result.data)
