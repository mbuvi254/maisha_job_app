from app.database.database import Database
import uuid


class JobRepository:

    def get_connection(self):
        return Database().get_connection()

    def fetch_by_employer_id(self, employer_id):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM jobs WHERE employer_id=%s ORDER BY created_at DESC",
            (employer_id,)
        )
        rows = cursor.fetchall()

        cursor.close()
        conn.close()
        return rows

    def fetch_by_id(self, job_id):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM jobs WHERE id=%s", (job_id,))
        row = cursor.fetchone()

        cursor.close()
        conn.close()
        return row

    def insert(self, data):
        conn = self.get_connection()
        cursor = conn.cursor()
        job_id = str(uuid.uuid4())

        cursor.execute(
            """
            INSERT INTO jobs (
                id, employer_id, title, description, skills, experience_level, ai_enabled, deadline
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                job_id,
                data.get("employer_id"),
                data.get("title"),
                data.get("description"),
                data.get("skills"),
                data.get("experience_level"),
                1 if data.get("ai_enabled") else 0,
                data.get("deadline"),
            )
        )
        conn.commit()

        cursor.close()
        conn.close()
        return job_id

    def update(self, job_id, data):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE jobs
            SET title=%s, description=%s, skills=%s, experience_level=%s, ai_enabled=%s, deadline=%s
            WHERE id=%s AND employer_id=%s
            """,
            (
                data.get("title"),
                data.get("description"),
                data.get("skills"),
                data.get("experience_level"),
                1 if data.get("ai_enabled") else 0,
                data.get("deadline"),
                job_id,
                data.get("employer_id"),
            )
        )
        conn.commit()
        updated = cursor.rowcount > 0

        cursor.close()
        conn.close()
        return updated

    def fetch_all(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM jobs ORDER BY created_at DESC")
        rows = cursor.fetchall()

        cursor.close()
        conn.close()
        return rows
