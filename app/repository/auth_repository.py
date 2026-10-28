"""Atomic OTP lifecycle backed by the application's MySQL database."""
import hashlib
import hmac
import time

from app.database.database import Database


class AuthRepository:
    def issue(self, challenge_id, role, email, code_hash):
        conn = Database().get_connection()
        lock = 'otp:' + hashlib.sha256(f'{role}:{email}'.encode()).hexdigest()[:55]
        try:
            with conn.cursor() as cursor:
                cursor.execute('SELECT GET_LOCK(%s, 5) AS acquired', (lock,))
                if not cursor.fetchone()['acquired']:
                    return False
                cursor.execute('SELECT issued_at FROM auth_challenges WHERE role=%s AND email=%s ORDER BY issued_at DESC LIMIT 1', (role, email))
                latest = cursor.fetchone()
                now = time.time()
                if latest and now - latest['issued_at'] < 60:
                    return False
                cursor.execute('UPDATE auth_challenges SET consumed=1 WHERE role=%s AND email=%s', (role, email))
                cursor.execute('INSERT INTO auth_challenges (id, role, email, code_hash, issued_at) VALUES (%s,%s,%s,%s,%s)', (challenge_id, role, email, code_hash, now))
                cursor.execute('DELETE FROM auth_challenges WHERE issued_at < %s', (now - 86400,))
                conn.commit()
                return True
        except Exception:
            conn.rollback()
            raise
        finally:
            with conn.cursor() as cursor:
                cursor.execute('SELECT RELEASE_LOCK(%s)', (lock,))
            conn.close()

    def discard(self, challenge_id):
        conn = Database().get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('DELETE FROM auth_challenges WHERE id=%s', (challenge_id,))
            conn.commit()
        finally:
            conn.close()

    def consume(self, challenge_id, role, email, code_hash):
        conn = Database().get_connection()
        try:
            conn.begin()
            with conn.cursor() as cursor:
                cursor.execute('SELECT * FROM auth_challenges WHERE id=%s AND role=%s AND email=%s FOR UPDATE', (challenge_id, role, email))
                row = cursor.fetchone()
                if not row or row['consumed'] or row['attempts'] >= 5 or time.time() - row['issued_at'] >= 600:
                    return False
                valid = hmac.compare_digest(row['code_hash'], code_hash)
                cursor.execute('UPDATE auth_challenges SET attempts=attempts+1, consumed=%s WHERE id=%s', (valid or row['attempts'] >= 4, challenge_id))
                conn.commit()
                return valid
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
