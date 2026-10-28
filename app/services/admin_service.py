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


DIRECTORIES = {
    'candidates': ('candidates', ['id', 'first_name', 'last_name', 'email', 'phone', 'created_at']),
    'employers': ('employers', ['id', 'firstName', 'lastName', 'email', 'phone', 'verified', 'created_at']),
    'jobs': ('jobs', ['id', 'title', 'employer_id', 'skills', 'deadline', 'created_at']),
    'resumes': ('candidates', ['id', 'first_name', 'last_name', 'email', 'cv_name', 'cv_uploaded_at']),
    'submitted-resumes': ('applications', ['id', 'user_id', 'job_id', 'resume_name', 'created_at']),
    'interviews': ('interviews', ['id', 'application_id', 'candidate_id', 'status', 'total_score', 'created_at']),
    'applications': ('applications', ['id', 'user_id', 'job_id', 'status', 'score', 'resume_name', 'created_at']),
}


def get_directory(kind, page=1, query=''):
    table, columns = DIRECTORIES[kind]
    where = ' WHERE cv_filename IS NOT NULL' if kind == 'resumes' else ' WHERE 1=1'
    if kind == 'submitted-resumes':
        where = " WHERE resume_path IS NOT NULL AND resume_path <> ''"
    params = []
    if query:
        where += ' AND (' + ' OR '.join(f'CAST({column} AS CHAR) LIKE %s' for column in columns) + ')'
        params = ['%' + query + '%'] * len(columns)
    conn = Database().get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(f'SELECT COUNT(*) count FROM {table}' + where, params)
            count = cursor.fetchone()['count']
            cursor.execute(f'SELECT {", ".join(columns)} FROM {table}' + where + ' ORDER BY ' + ('cv_uploaded_at' if kind == 'resumes' else 'created_at') + ' DESC LIMIT 50 OFFSET %s', params + [(page-1)*50])
            rows = cursor.fetchall()
        return dict(columns=columns, rows=rows, count=count, page=page, kind=kind, query=query)
    finally:
        conn.close()


def get_growth():
    from datetime import date, timedelta
    days = [(date.today()-timedelta(days=i)).isoformat() for i in range(29, -1, -1)]
    result = dict(days=days, series={}, totals={})
    conn = Database().get_connection()
    try:
        with conn.cursor() as cursor:
            for label, table, field, condition in [
                ('Candidates', 'candidates', 'created_at', '1=1'),
                ('Employers', 'employers', 'created_at', '1=1'),
                ('Jobs', 'jobs', 'created_at', '1=1'),
                ('Profile resumes', 'candidates', 'cv_uploaded_at', 'cv_filename IS NOT NULL'),
                ('Submitted resumes', 'applications', 'created_at', "resume_path IS NOT NULL AND resume_path <> ''")]:
                cursor.execute(f'SELECT COUNT(*) count FROM {table} WHERE {condition}')
                result['totals'][label] = cursor.fetchone()['count']
                cursor.execute(f'SELECT DATE({field}) day, COUNT(*) count FROM {table} WHERE {condition} AND {field} >= %s GROUP BY DATE({field})', (days[0],))
                counts = {str(row['day']): row['count'] for row in cursor.fetchall()}
                result['series'][label] = [counts.get(day, 0) for day in days]
        return result
    finally:
        conn.close()
