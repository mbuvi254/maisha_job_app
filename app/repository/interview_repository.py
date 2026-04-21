import uuid

from app.database.database import Database


class InterviewRepository:
    def get_connection(self):
        return Database().get_connection()

    def insert(self, data):
        conn = self.get_connection()
        cursor = conn.cursor()
        interview_id = str(uuid.uuid4())

        cursor.execute(
            """
            INSERT INTO interviews (
                id, application_id, candidate_id, role, total_score, response_count, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                interview_id,
                data.get("application_id"),
                data.get("candidate_id"),
                data.get("role"),
                data.get("total_score", 0),
                data.get("response_count", 0),
                data.get("status", "in_progress"),
            )
        )
        conn.commit()

        cursor.close()
        conn.close()
        return interview_id

    def fetch_by_id(self, interview_id):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM interviews WHERE id=%s", (interview_id,))
        row = cursor.fetchone()

        cursor.close()
        conn.close()
        return row

    def fetch_by_application_id(self, application_id):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM interviews WHERE application_id=%s ORDER BY created_at DESC LIMIT 1",
            (application_id,)
        )
        row = cursor.fetchone()

        cursor.close()
        conn.close()
        return row

    def insert_response(self, data):
        conn = self.get_connection()
        cursor = conn.cursor()
        response_id = str(uuid.uuid4())

        cursor.execute(
            """
            INSERT INTO interview_responses (
                id, interview_id, question, answer, score, feedback
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                response_id,
                data.get("interview_id"),
                data.get("question"),
                data.get("answer"),
                data.get("score", 0),
                data.get("feedback"),
            )
        )
        conn.commit()

        cursor.close()
        conn.close()
        return response_id

    def fetch_responses_by_interview_id(self, interview_id):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM interview_responses WHERE interview_id=%s ORDER BY created_at ASC",
            (interview_id,)
        )
        rows = cursor.fetchall()

        cursor.close()
        conn.close()
        return rows

    def update_totals(self, interview_id, score_delta):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE interviews
            SET total_score = total_score + %s,
                response_count = response_count + 1
            WHERE id = %s
            """,
            (score_delta, interview_id)
        )
        conn.commit()

        cursor.close()
        conn.close()

    def mark_completed(self, interview_id):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE interviews SET status='completed' WHERE id=%s",
            (interview_id,)
        )
        conn.commit()

        cursor.close()
        conn.close()

