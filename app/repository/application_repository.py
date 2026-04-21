import uuid

from app.database.database import Database


class ApplicationRepository:

    def get_connection(self):
        return Database().get_connection()

    def fetch_by_job_id(self, job_id):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM applications WHERE job_id=%s ORDER BY created_at DESC",
            (job_id,)
        )
        rows = cursor.fetchall()

        cursor.close()
        conn.close()
        return rows

    def fetch_by_candidate_and_job(self, candidate_id, job_id):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM applications WHERE user_id=%s AND job_id=%s LIMIT 1",
            (candidate_id, job_id)
        )
        row = cursor.fetchone()

        cursor.close()
        conn.close()
        return row

    def fetch_by_id(self, application_id):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM applications WHERE id=%s LIMIT 1",
            (application_id,)
        )
        row = cursor.fetchone()

        cursor.close()
        conn.close()
        return row

    def update_status(self, application_id, status):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE applications SET status=%s WHERE id=%s",
            (status, application_id)
        )
        conn.commit()
        updated = cursor.rowcount > 0

        cursor.close()
        conn.close()
        return updated

    def update_status_and_score(self, application_id, status, score):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE applications SET status=%s, score=%s WHERE id=%s",
            (status, score, application_id)
        )
        conn.commit()
        updated = cursor.rowcount > 0

        cursor.close()
        conn.close()
        return updated

    def update_score(self, application_id, score):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE applications SET score=%s WHERE id=%s",
            (score, application_id)
        )
        conn.commit()
        updated = cursor.rowcount > 0

        cursor.close()
        conn.close()
        return updated

    def insert(self, data):
        conn = self.get_connection()
        cursor = conn.cursor()
        application_id = str(uuid.uuid4())

        cursor.execute(
            """
            INSERT INTO applications (id, job_id, user_id, status, score)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                application_id,
                data.get("job_id"),
                data.get("user_id"),
                data.get("status", "submitted"),
                data.get("score", 0),
            )
        )
        conn.commit()

        cursor.close()
        conn.close()
        return application_id
