import unittest
from app import app


class RecoveryPageTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True,SECRET_KEY='test')
        self.client=app.test_client()

    def test_missing_page_is_branded_with_404_status(self):
        response=self.client.get('/missing/page/does-not-exist')
        self.assertEqual(response.status_code,404)
        self.assertIn(b'This page could not be found',response.data)
        self.assertIn(b'Go to home',response.data)
        self.assertIn('no-store',response.headers['Cache-Control'])

    def test_error_routes_have_correct_status_and_no_private_details(self):
        for code in [400,401,403,404,405,410,413,429,500,502,503,504]:
            with self.subTest(code=code):
                response=self.client.get('/errors/'+str(code))
                self.assertEqual(response.status_code,code)
                self.assertIn(b'Maisha Jobs',response.data)
                self.assertNotIn(b'Traceback',response.data)
        self.assertEqual(self.client.get('/errors/123').status_code,404)

    def test_json_clients_keep_json_errors(self):
        response=self.client.post('/missing/api/endpoint',json={'input':'value'})
        self.assertEqual(response.status_code,404)
        self.assertEqual(response.json['status'],404)
        response=self.client.get('/missing/api/endpoint',headers={'Accept':'application/json'})
        self.assertEqual(response.status_code,404)
        self.assertTrue(response.is_json)

    def test_method_not_allowed_preserves_allow_header(self):
        response=self.client.post('/offline')
        self.assertEqual(response.status_code,405)
        self.assertIn('GET',response.headers['Allow'])

    def test_offline_page_is_public_and_self_contained(self):
        with self.client.session_transaction() as session:
            session['candidate_email']='private@example.invalid'
        response=self.client.get('/offline')
        self.assertEqual(response.status_code,200)
        self.assertIn(b'Try again',response.data)
        self.assertNotIn(b'private@example.invalid',response.data)
        self.assertNotIn(b'cdn.jsdelivr',response.data)
        self.assertNotIn(b'fonts.googleapis',response.data)

    def test_worker_is_served_at_root_with_scope_permission(self):
        response=self.client.get('/service-worker.js')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.mimetype,'application/javascript')
        self.assertEqual(response.headers['Service-Worker-Allowed'],'/')
        self.assertEqual(response.headers['Cache-Control'],'no-cache')
        self.assertIn(b"const OFFLINE_PAGE = '/offline'",response.data)
        response.close()
