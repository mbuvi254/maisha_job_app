import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import app
from app.services.candidate_resume_service import cv_directory, find_profile_cv, find_application_resume
from app.services.resume_ai_service import _resume_file_path


class ResumeStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.configured=self.root/'persistent'
        self.legacy=self.root/'private'/'candidate_resumes'
        self.static=self.root/'static'/'resumes'
        self.legacy.mkdir(parents=True)
        self.static.mkdir(parents=True)
        self.settings=dict(app.config)
        self.addCleanup(lambda:app.config.update(self.settings))
        app.config.update(TESTING=True,SECRET_KEY='test',CV_STORAGE_DIRECTORY=str(self.configured))
        self.patch=patch.object(app,'root_path',str(self.root))
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.client=app.test_client()
        self.candidate={'id':'candidate','cv_filename':'cv.pdf','cv_name':'My resume.pdf'}
        self.application={'id':'application','job_id':'job','user_id':'candidate','resume_path':'candidate_cvs/cv.pdf','resume_name':'My resume.pdf'}

    def test_configured_storage_and_exact_legacy_lookup(self):
        (self.legacy/'cv.pdf').write_bytes(b'%PDF-1.4 test')
        (self.static/'old.pdf').write_bytes(b'%PDF-1.4 old')
        with app.app_context():
            self.assertEqual(cv_directory(),self.configured)
            self.assertEqual(find_profile_cv('cv.pdf'),self.legacy/'cv.pdf')
            self.assertEqual(_resume_file_path('candidate_cvs/cv.pdf'),str(self.legacy/'cv.pdf'))
            self.assertEqual(find_application_resume('resumes/old.pdf'),self.static/'old.pdf')
            for name in ['../cv.pdf','nested/cv.pdf','..\\cv.pdf','/etc/passwd']:
                self.assertIsNone(find_profile_cv(name))
            self.assertIsNone(find_application_resume('resumes/../old.pdf'))
            self.assertIsNone(find_application_resume('/etc/passwd'))

    def test_candidate_can_view_legacy_pdf_inline(self):
        (self.legacy/'cv.pdf').write_bytes(b'%PDF-1.4 test')
        with self.client.session_transaction() as session:
            session['candidate_id']='candidate'
        with patch('app.blueprints.candidate_bp.get_candidate_by_id',return_value=self.candidate):
            response=self.client.get('/candidates/profile/cv')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data,b'%PDF-1.4 test')
        self.assertTrue(response.headers['Content-Disposition'].startswith('inline'))
        self.assertIn('no-store',response.headers['Cache-Control'])
        response.close()

    def test_missing_profile_file_guides_owner_to_reupload(self):
        with self.client.session_transaction() as session:
            session['candidate_id']='candidate'
        with patch('app.blueprints.candidate_bp.get_candidate_by_id',return_value=self.candidate):
            response=self.client.get('/candidates/profile/cv')
        self.assertEqual(response.status_code,302)
        self.assertTrue(response.location.endswith('/candidates/profile#my-cv'))
        with self.client.session_transaction() as session:
            self.assertIn('Please upload it again',str(session.get('_flashes')))

    def test_employer_can_view_applicant_cv_but_other_employers_cannot(self):
        (self.legacy/'cv.pdf').write_bytes(b'%PDF-1.4 original')
        with self.client.session_transaction() as session:
            session['employer_id']='employer'
        with patch('app.blueprints.jobs_bp.get_application_by_id',return_value=self.application), patch('app.blueprints.jobs_bp.get_job_by_id',return_value={'id':'job','employer_id':'employer'}):
            response=self.client.get('/applications/application/resume')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data,b'%PDF-1.4 original')
        response.close()
        with patch('app.blueprints.jobs_bp.get_application_by_id',return_value=self.application), patch('app.blueprints.jobs_bp.get_job_by_id',return_value={'id':'job','employer_id':'other'}):
            self.assertEqual(self.client.get('/applications/application/resume').status_code,404)

    def test_missing_employer_resume_explains_recovery_without_substituting_cv(self):
        with self.client.session_transaction() as session:
            session['employer_id']='employer'
        # Use real template paths while the missing file is resolved in configured private storage.
        self.patch.stop()
        with patch('app.blueprints.jobs_bp.get_application_by_id',return_value=self.application), patch('app.blueprints.jobs_bp.get_job_by_id',return_value={'id':'job','employer_id':'employer'}):
            response=self.client.get('/applications/application/resume')
        self.assertEqual(response.status_code,410)
        self.assertIn(b'The original resume file is unavailable',response.data)
        self.assertIn(b'Back to application',response.data)
