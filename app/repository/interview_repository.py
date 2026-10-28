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


    def save_plan(self, interview_id, plan):
        import json
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE interviews SET question_plan=%s WHERE id=%s AND question_plan IS NULL",
                           (json.dumps(plan), interview_id))
            conn.commit()
            cursor.close()
        finally:
            conn.close()

    def insert_response_once(self, data, expected_count):
        """Serialize submissions so retries cannot advance or score a slot twice."""
        conn = self.get_connection()
        try:
            conn.begin()
            cursor = conn.cursor()
            cursor.execute("SELECT response_count, status FROM interviews WHERE id=%s FOR UPDATE",
                           (data["interview_id"],))
            row = cursor.fetchone()
            cursor.execute("SELECT COUNT(*) AS count FROM interview_responses WHERE interview_id=%s",
                           (data["interview_id"],))
            actual = cursor.fetchone()["count"]
            if not row or row["status"] == "completed" or actual != expected_count:
                conn.rollback()
                cursor.close()
                return False
            cursor.execute("""INSERT INTO interview_responses
                (id, interview_id, question, answer, score, feedback, expected_answer, question_number, evaluation_status, answer_html)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (data.get("id") or str(uuid.uuid4()), data["interview_id"], data["question"], data["answer"],
                 data["score"], data["feedback"], data["expected_answer"], expected_count + 1, data.get("evaluation_status", "completed"), data.get("answer_html")))
            cursor.execute("""UPDATE interviews SET total_score=total_score+%s,
                response_count=%s WHERE id=%s""",
                (data["score"] or 0, actual + 1, data["interview_id"]))
            if data.get("score") is None:
                cursor.execute("""UPDATE applications a JOIN interviews i ON i.application_id=a.id
                    SET a.score=NULL WHERE i.id=%s""", (data["interview_id"],))
            conn.commit()
            cursor.close()
            return True
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def finish_evaluation(self, interview_id, response_id, evaluation):
        conn = self.get_connection()
        try:
            conn.begin()
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM interviews WHERE id=%s FOR UPDATE", (interview_id,))
                cursor.fetchone()
                cursor.execute("SELECT * FROM interview_responses WHERE id=%s AND interview_id=%s FOR UPDATE",
                               (response_id, interview_id))
                row = cursor.fetchone()
                if not row:
                    raise RuntimeError("Saved response not found")
                if row.get("evaluation_status") == "completed":
                    conn.commit()
                    return row
                cursor.execute("""UPDATE interview_responses SET score=%s, feedback=%s,
                    expected_answer=%s, evaluation_status='completed' WHERE id=%s""",
                    (evaluation['score'], evaluation['feedback'], evaluation['expected_answer'], response_id))
                cursor.execute("""UPDATE interviews SET total_score=(
                    SELECT COALESCE(SUM(score),0) FROM interview_responses WHERE interview_id=%s)
                    WHERE id=%s""", (interview_id, interview_id))
            conn.commit()
            return dict(row, **evaluation, evaluation_status="completed")
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
