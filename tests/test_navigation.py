import unittest
from unittest.mock import patch

from app import app


class NavigationTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, SECRET_KEY='test')
        self.client = app.test_client()

    def test_categories_show_live_counts_and_filter_links(self):
        groups = [dict(industry=dict(id='tech', name='Technology'),
                       categories=[dict(id='software', name='Software Engineering')])]
        with patch('app.blueprints.jobs_bp.get_grouped_categories', return_value=groups), patch(
                'app.blueprints.jobs_bp.get_all_jobs', return_value=[dict(id='job', category_id='software')]) as jobs:
            response = self.client.get('/categories')
        self.assertEqual(response.status_code, 200)
        for content in ('Home', 'Browse Jobs', 'Categories', 'AI Job Match', 'Find Jobs',
                        'Switch to dark mode', 'Software Engineering', '1 open roles', 'category_id=software'):
            self.assertIn(content.encode(), response.data)
        self.assertIn(b'aria-current="page"', response.data)
        self.assertIn(b'id="siteNavigation"', response.data)
        jobs.assert_called_once_with(hide_expired=True)

    def test_guest_match_page_and_candidate_destination(self):
        response = self.client.get('/job-match')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Upload &amp; find matches', response.data)
        with self.client.session_transaction() as session:
            session['candidate_id'] = 'candidate'
        response = self.client.get('/job-match')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/candidates/matches'))

    def test_empty_categories_page_is_usable(self):
        with patch('app.blueprints.jobs_bp.get_grouped_categories', return_value=[]), patch(
                'app.blueprints.jobs_bp.get_all_jobs', return_value=[]):
            response = self.client.get('/categories')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Categories are on their way', response.data)
