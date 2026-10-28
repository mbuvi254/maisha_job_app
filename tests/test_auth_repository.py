"""Opt-in MySQL checks. All writes are isolated to a unique test identity."""
import os
import secrets
import time
import unittest
from concurrent.futures import ThreadPoolExecutor

from app.database.database import Database
from app.repository.auth_repository import AuthRepository


@unittest.skipUnless(os.getenv('AUTH_TEST_MYSQL') == '1', 'Set AUTH_TEST_MYSQL=1 for local database integration checks')
class RepositoryIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.repo=AuthRepository()
        self.email=f'otp-test-{secrets.token_hex(8)}@example.invalid'
        self.ident=secrets.token_hex(32)
        self.code_hash='a'*64
        self.assertTrue(self.repo.issue(self.ident,'candidate',self.email,self.code_hash))
        self.addCleanup(self.cleanup_rows)

    def cleanup_rows(self):
        conn=Database().get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('DELETE FROM auth_challenges WHERE email=%s',(self.email,))
            conn.commit()
        finally:
            conn.close()

    def age_code(self, seconds):
        conn=Database().get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('UPDATE auth_challenges SET issued_at=%s WHERE id=%s',(time.time()-seconds,self.ident))
            conn.commit()
        finally:
            conn.close()

    def test_atomic_single_use_under_concurrent_requests(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes=list(executor.map(lambda _:self.repo.consume(self.ident,'candidate',self.email,self.code_hash),range(2)))
        self.assertEqual(sorted(outcomes),[False,True])

    def test_expiry_is_enforced_by_database_record(self):
        self.age_code(601)
        self.assertFalse(self.repo.consume(self.ident,'candidate',self.email,self.code_hash))

    def test_attempt_limit_persists(self):
        for _ in range(5):
            self.assertFalse(self.repo.consume(self.ident,'candidate',self.email,'b'*64))
        self.assertFalse(self.repo.consume(self.ident,'candidate',self.email,self.code_hash))

    def test_role_isolation(self):
        self.assertFalse(self.repo.consume(self.ident,'admin',self.email,self.code_hash))
        self.assertTrue(self.repo.consume(self.ident,'candidate',self.email,self.code_hash))

    def test_cooldown_and_replacement(self):
        new_id=secrets.token_hex(32)
        self.assertFalse(self.repo.issue(new_id,'candidate',self.email,'b'*64))
        self.age_code(61)
        self.assertTrue(self.repo.issue(new_id,'candidate',self.email,'b'*64))
        self.assertFalse(self.repo.consume(self.ident,'candidate',self.email,self.code_hash))
        self.assertTrue(self.repo.consume(new_id,'candidate',self.email,'b'*64))
