import json
import unittest
from datetime import datetime
from unittest.mock import patch
from app import app
from app.services.resume_ai_service import analyze_resume_fit


class ResumeTimestampTests(unittest.TestCase):
    def test_ai_and_fallback_results_have_completion_times(self):
        with app.app_context():
            for text in ['', 'Python engineer with SQL experience']:
                with self.subTest(text=text), patch('app.services.resume_ai_service._resume_file_path',return_value=None), patch('app.services.resume_ai_service._extract_resume_text',return_value=text), patch('app.services.resume_ai_service.call_ai',return_value=json.dumps(dict(score=65,fit_label='Partial fit',summary='Review required'))):
                    before=datetime.now()
                    result=analyze_resume_fit({'title':'Engineer','skills':'Python'},{'first_name':'Amina'},'cv.pdf')
                    self.assertIsInstance(result['analyzed_at'],datetime)
                    self.assertGreaterEqual(result['analyzed_at'],before)
                    self.assertLessEqual(result['analyzed_at'],datetime.now())
                    self.assertEqual(result['source'],'ai' if text else 'heuristic')

    def test_refresh_requires_signin_csrf_and_job_ownership(self):
        app.config.update(TESTING=True,SECRET_KEY='test')
        client=app.test_client()
        url='/employers/jobs/job/applications/application/analyze-resume'
        self.assertEqual(client.post(url).status_code,401)
        with client.session_transaction() as session:
            session['employer_id']='employer'
            session['auth_csrf']='csrf'
        self.assertEqual(client.post(url).status_code,400)
        with patch('app.blueprints.employer_bp.get_job_by_id',return_value={'id':'job','employer_id':'other'}), patch('app.blueprints.employer_bp.analyze_resume_fit') as analyze:
            self.assertEqual(client.post(url,data={'csrf_token':'csrf'}).status_code,404)
            analyze.assert_not_called()

    def test_refresh_saves_actual_analysis_timestamp(self):
        app.config.update(TESTING=True,SECRET_KEY='test')
        client=app.test_client()
        with client.session_transaction() as session:
            session['employer_id']='employer'
            session['auth_csrf']='csrf'
        result={'score':65,'analyzed_at':datetime(2026,10,28,12,40)}
        with patch('app.blueprints.employer_bp.get_job_by_id',return_value={'id':'job','employer_id':'employer'}), patch('app.blueprints.employer_bp.get_application_by_id',return_value={'id':'application','job_id':'job','user_id':'candidate','resume_path':'cv.pdf'}), patch('app.blueprints.employer_bp.get_candidate_by_id',return_value={'id':'candidate'}), patch('app.blueprints.employer_bp.analyze_resume_fit',return_value=result), patch('app.blueprints.employer_bp.update_application_resume_analysis') as save:
            response=client.post('/employers/jobs/job/applications/application/analyze-resume',data={'csrf_token':'csrf'})
        self.assertEqual(response.status_code,302)
        save.assert_called_once_with('application',result)
