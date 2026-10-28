import time
import unittest
from unittest.mock import patch

from app import app
from app.blueprints import auth_bp as auth


class MemoryChallenges:
    def __init__(self):
        self.rows = {}

    def issue(self, ident, role, email, code_hash):
        now = time.time()
        if any(r['role'] == role and r['email'] == email and now-r['issued_at'] < 60 for r in self.rows.values()):
            return False
        for row in self.rows.values():
            if (row['role'], row['email']) == (role, email):
                row['consumed'] = True
        self.rows[ident] = dict(role=role, email=email, code_hash=code_hash, issued_at=now, attempts=0, consumed=False)
        return True

    def discard(self, ident):
        self.rows.pop(ident, None)

    def consume(self, ident, role, email, code_hash):
        row = self.rows.get(ident)
        if not row or (row['role'], row['email']) != (role, email) or row['consumed'] or row['attempts'] >= 5 or time.time()-row['issued_at'] >= 600:
            return False
        row['attempts'] += 1
        valid = row['code_hash'] == code_hash
        row['consumed'] = valid or row['attempts'] >= 5
        return valid


class AuthTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, SECRET_KEY='test-secret', ADMIN_EMAILS=['admin@example.invalid'])
        self.client = app.test_client()
        self.store = MemoryChallenges()
        self.patches = [patch.object(auth, 'repo', self.store), patch.object(auth, 'generate_otp', return_value='123456'), patch.object(auth, 'send_verification_email', return_value=True), patch.object(auth, 'get_candidate_by_email', side_effect=lambda email: {'id':'candidate-1','email':email}), patch.object(auth, 'get_employer_by_email', side_effect=lambda email: {'id':'employer-1','email':email}), patch.object(auth, 'set_employer_verified_status', return_value={'verified': True})]
        self.mocks = [p.start() for p in self.patches]
        self.addCleanup(lambda: [p.stop() for p in reversed(self.patches)])

    def token(self):
        with self.client.session_transaction() as s:
            return s['auth_csrf']

    def start(self, role='candidate', email=None, next_url=''):
        base = {'candidate':'candidates','employer':'employers','admin':'admin'}[role]
        self.client.get(f'/{base}/login{next_url}')
        return self.client.post(f'/{base}/login', data={'csrf_token':self.token(),'email':email or f'{role}@example.invalid'})

    def verify(self, base='candidates', code='123456'):
        return self.client.post(f'/{base}/verify', data={'csrf_token':self.token(),'otp':code})

    def test_three_roles_can_sign_in(self):
        for role, base in [('candidate','candidates'),('employer','employers'),('admin','admin')]:
            with self.subTest(role=role):
                self.client = app.test_client()
                self.assertEqual(self.start(role).status_code,302)
                with self.client.session_transaction() as s:
                    self.assertNotIn(f'{role}_id',s)
                    self.assertNotIn('123456',str(dict(s)))
                self.assertEqual(self.verify(base).status_code,302)
                with self.client.session_transaction() as s:
                    self.assertIn(f'{role}_id',s)
                    self.assertNotIn(f'{role}_challenge',s)

    def test_unlisted_admin_cannot_request_code(self):
        self.assertEqual(self.start('admin','outsider@example.invalid').status_code,400)
        self.mocks[2].assert_not_called()

    def test_empty_admin_allowlist_denies_access(self):
        app.config['ADMIN_EMAILS']=[]
        self.assertEqual(self.start('admin').status_code,400)

    def test_csrf_required(self):
        self.assertEqual(self.client.post('/candidates/login',data={'email':'test@example.invalid'}).status_code,400)

    def test_wrong_and_expired_codes(self):
        self.start()
        self.assertEqual(self.verify(code='000000').status_code,400)
        next(iter(self.store.rows.values()))['issued_at'] -= 601
        self.assertEqual(self.verify().status_code,400)

    def test_five_attempt_limit(self):
        self.start()
        for _ in range(5):
            self.assertEqual(self.verify(code='000000').status_code,400)
        self.assertEqual(self.verify().status_code,400)

    def test_resend_throttles_and_invalidates_previous_code(self):
        self.start()
        data={'csrf_token':self.token()}
        self.assertEqual(self.client.post('/candidates/resend-otp',data=data).status_code,429)
        old=next(iter(self.store.rows.values()));old['issued_at']-=61
        self.mocks[1].return_value='654321'
        self.assertEqual(self.client.post('/candidates/resend-otp',data=data).status_code,200)
        self.assertTrue(old['consumed'])
        self.assertEqual(self.verify().status_code,400)
        self.assertEqual(self.verify(code='654321').status_code,302)

    def test_failed_delivery_can_retry(self):
        self.mocks[2].return_value=False
        self.assertEqual(self.start().status_code,503)
        with self.client.session_transaction() as s:
            self.assertNotIn('candidate_challenge',s)
        self.assertFalse(self.store.rows)
        self.mocks[2].return_value=True
        self.assertEqual(self.start().status_code,302)

    def test_next_is_preserved_and_external_redirect_rejected(self):
        self.start(next_url='?next=/candidates/profile')
        self.assertEqual(self.verify().location,'/candidates/profile')
        for value in ['//evil.example','/\\evil.example','https://evil.example','/\nevil']:
            self.assertIsNone(auth.safe_next(value))

    def test_restart_allows_email_change(self):
        self.start()
        self.assertEqual(self.client.get('/candidates/login?restart=1').status_code,200)
        with self.client.session_transaction() as s:
            self.assertNotIn('candidate_challenge',s)

    def test_role_isolation_and_session_rotation(self):
        self.start()
        self.assertEqual(self.client.get('/employers/verify').location,'/employers/login')
        with self.client.session_transaction() as s:
            s['employer_id']='old-employer'
        self.verify()
        with self.client.session_transaction() as s:
            self.assertNotIn('employer_id',s)
            self.assertEqual(s['candidate_id'],'candidate-1')

    def test_admin_dashboard_requires_allowlisted_session(self):
        self.assertEqual(self.client.get('/admin/dashboard').status_code,302)
        with self.client.session_transaction() as s:
            s['admin_id']='outsider';s['admin_email']='outsider@example.invalid'
        self.assertEqual(self.client.get('/admin/dashboard').status_code,302)

    def test_admin_allowlist_rechecked_after_code_sent(self):
        self.start('admin')
        app.config['ADMIN_EMAILS']=[]
        self.assertEqual(self.verify('admin').status_code,403)

    def test_authenticated_pages_are_never_cached(self):
        self.assertEqual(self.client.get('/candidates/login').headers['Cache-Control'],'no-store')

    def test_resend_is_post_only(self):
        self.assertEqual(self.client.get('/candidates/resend-otp').status_code,405)

    def test_employer_api_requires_authentication(self):
        self.assertEqual(self.client.get('/employers/').status_code,403)
        self.assertEqual(self.client.delete('/employers/other').status_code,403)
        self.assertEqual(self.client.put('/employers/other',json={}).status_code,401)

    def test_registration_templates_and_csrf(self):
        for base in ['candidates','employers']:
            response=self.client.get(f'/{base}/register')
            self.assertEqual(response.status_code,200)
            self.assertIn(b'csrf_token',response.data)
            self.assertEqual(self.client.post(f'/{base}/register',data={}).status_code,400)

    def test_home_search_combines_with_existing_filters(self):
        jobs=[dict(id='1',title='Python engineer',skills='Flask',experience_level='Senior'),dict(id='2',title='Designer',skills='Figma')]
        with patch('app.blueprints.jobs_bp.get_all_jobs', return_value=jobs) as get_jobs, patch('app.blueprints.jobs_bp.get_industries',return_value=[]),patch('app.blueprints.jobs_bp.get_grouped_categories',return_value=[]):
            response=self.client.get('/?q=python+flask&experience_level=Senior')
            self.assertEqual(response.status_code,200)
            self.assertIn(b'Python engineer',response.data)
            self.assertNotIn(b'Designer',response.data)
            self.assertEqual(get_jobs.call_args.kwargs['experience_level'],'Senior')

    def test_legacy_pending_session_recovers(self):
        with self.client.session_transaction() as session:
            session['pending_verification']=True
            session['employer_id']='unverified-old-account'
        response=self.client.get('/employers/login')
        self.assertEqual(response.status_code,200)
        with self.client.session_transaction() as session:
            self.assertNotIn('employer_id',session)
            self.assertNotIn('pending_verification',session)

    def test_registration_requires_otp_before_authentication(self):
        for role,base,first,last,module in [('candidate','candidates','first_name','last_name','candidate_bp'),('employer','employers','firstName','lastName','employer_bp')]:
            with self.subTest(role=role):
                self.client=app.test_client()
                self.client.get(f'/{base}/register')
                lookup = 'get_candidate_by_email' if role == 'candidate' else '_lookup_employer'
                create = 'get_or_create_candidate' if role == 'candidate' else 'create_employer'
                with patch(f'app.blueprints.{module}.{lookup}',return_value=None), patch(f'app.blueprints.{module}.{create}',return_value={'id':f'{role}-1'}):
                    response=self.client.post(f'/{base}/register',data={'csrf_token':self.token(),first:'Test',last:'Account','email':f'register-{role}@example.invalid'})
                self.assertEqual(response.status_code,302)
                with self.client.session_transaction() as session:
                    self.assertNotIn(f'{role}_id',session)
                    self.assertIn(f'{role}_challenge',session)
                self.assertEqual(self.verify(base).status_code,302)

    def test_all_templates_compile(self):
        for template in app.jinja_env.list_templates():
            app.jinja_env.get_template(template)


if __name__ == '__main__':
    unittest.main()
