from app.database.database import Database


def get_platform_activity():
    """Aggregate platform activity and bound the detailed directory preview."""
    conn = Database().get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""SELECT
                (SELECT COUNT(*) FROM candidates) AS candidates,
                (SELECT COUNT(*) FROM applications) AS applications,
                (SELECT COUNT(*) FROM interviews WHERE status='completed') AS completed_interviews,
                (SELECT COUNT(*) FROM interviews WHERE status='in_progress') AS active_interviews,
                (SELECT COUNT(*) FROM interview_responses) AS answers,
                (SELECT ROUND(AVG(score), 1) FROM interview_responses) AS average_score""")
            totals = cursor.fetchone()
            cursor.execute("SELECT status, COUNT(*) AS count FROM applications GROUP BY status ORDER BY count DESC")
            statuses = cursor.fetchall()
            cursor.execute("""SELECT a.id, a.job_id, a.status, a.created_at, j.title,
                c.first_name, c.last_name FROM applications a
                LEFT JOIN jobs j ON j.id=a.job_id LEFT JOIN candidates c ON c.id=a.user_id
                ORDER BY a.created_at DESC LIMIT 10""")
            recent = cursor.fetchall()
        return dict(totals=totals, statuses=statuses, recent=recent)
    finally:
        conn.close()
