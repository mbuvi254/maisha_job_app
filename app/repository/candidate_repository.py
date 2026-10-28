import uuid

from app.database.database import Database


class CandidateRepository:

    def get_connection(self):
        return Database().get_connection()

    def fetch_by_email(self, email):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM candidates WHERE email=%s", (email,))
        row = cursor.fetchone()

        cursor.close()
        conn.close()
        return row

    def fetch_by_id(self, candidate_id):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM candidates WHERE id=%s", (candidate_id,))
        row = cursor.fetchone()

        cursor.close()
        conn.close()
        return row

    def insert(self, data):
        conn = self.get_connection()
        cursor = conn.cursor()
        candidate_id = str(uuid.uuid4())

        cursor.execute(
            """
            INSERT INTO candidates (id, first_name, last_name, email, phone)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                candidate_id,
                data.get("first_name"),
                data.get("last_name"),
                data.get("email"),
                data.get("phone"),
            )
        )
        conn.commit()

        cursor.close()
        conn.close()
        return candidate_id

    def update_cv(self, candidate_id, data):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""UPDATE candidates SET cv_filename=%s, cv_name=%s,
                    cv_text=%s, cv_uploaded_at=NOW() WHERE id=%s""",
                    (data['cv_filename'], data['cv_name'], data['cv_text'], candidate_id))
            conn.commit()
        finally:
            conn.close()
