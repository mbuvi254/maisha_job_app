import uuid

from app.database.database import Database


class SavedJobRepository:

    def get_connection(self):
        return Database().get_connection()

    def fetch_by_candidate_and_job(self, candidate_id, job_id):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM saved_jobs
            WHERE candidate_id=%s AND job_id=%s
            LIMIT 1
            """,
            (candidate_id, job_id),
        )
        row = cursor.fetchone()

        cursor.close()
        conn.close()
        return row

    def fetch_by_candidate_id(self, candidate_id):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                sj.id AS saved_job_id,
                sj.created_at AS saved_at,
                j.*
            FROM saved_jobs sj
            INNER JOIN jobs j ON j.id = sj.job_id
            WHERE sj.candidate_id=%s
            ORDER BY sj.created_at DESC
            """,
            (candidate_id,),
        )
        rows = cursor.fetchall()

        cursor.close()
        conn.close()
        return rows

    def insert(self, candidate_id, job_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        saved_job_id = str(uuid.uuid4())

        cursor.execute(
            """
            INSERT INTO saved_jobs (id, candidate_id, job_id)
            VALUES (%s, %s, %s)
            """,
            (saved_job_id, candidate_id, job_id),
        )
        conn.commit()

        cursor.close()
        conn.close()
        return saved_job_id

    def delete(self, candidate_id, job_id):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            DELETE FROM saved_jobs
            WHERE candidate_id=%s AND job_id=%s
            """,
            (candidate_id, job_id),
        )
        conn.commit()
        deleted = cursor.rowcount > 0

        cursor.close()
        conn.close()
        return deleted
