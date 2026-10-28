"""Local request analytics and short-lived private guest resumes."""
from contextlib import contextmanager
import json
import secrets
import sqlite3
import time
from pathlib import Path
from flask import current_app


@contextmanager
def connect():
    path = Path(current_app.config.get('ACTIVITY_DATABASE') or Path(current_app.instance_path) / 'activity.sqlite3')
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=2)
    conn.row_factory = sqlite3.Row
    conn.executescript('''CREATE TABLE IF NOT EXISTS requests (
        id INTEGER PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        path TEXT, method TEXT, status INTEGER, duration_ms INTEGER, role TEXT);
        CREATE INDEX IF NOT EXISTS request_date ON requests(created_at);
        CREATE TABLE IF NOT EXISTS guest_resumes (
        token TEXT PRIMARY KEY, created_at REAL, data TEXT);
        CREATE TABLE IF NOT EXISTS resume_events (
        id INTEGER PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP, role TEXT);''')
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def save_guest(data):
    token = secrets.token_urlsafe(32)
    with connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        expired = conn.execute('SELECT data FROM guest_resumes WHERE created_at < ?', (time.time()-86400,)).fetchall()
        from app.services.candidate_resume_service import cv_directory
        for row in expired:
            (cv_directory() / json.loads(row['data'])['cv_filename']).unlink(missing_ok=True)
        conn.execute('DELETE FROM guest_resumes WHERE created_at < ?', (time.time()-86400,))
        conn.execute('INSERT INTO guest_resumes VALUES (?,?,?)', (token, time.time(), json.dumps(data)))
        conn.execute("INSERT INTO resume_events(role) VALUES ('guest')")
    return token


def guest_resume(token):
    if not token:
        return None
    with connect() as conn:
        row = conn.execute('SELECT data FROM guest_resumes WHERE token=? AND created_at>=?', (token, time.time()-86400)).fetchone()
    return json.loads(row['data']) if row else None


def claim_guest(token, candidate_id):
    if not token:
        return None
    # Serialize claims and cleanup so a guest file can acquire only one owner.
    with connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT data FROM guest_resumes WHERE token=? AND created_at>=?',
                           (token, time.time()-86400)).fetchone()
        if not row:
            return None
        data = json.loads(row['data'])
        from app.services.candidate_service import update_candidate_cv
        update_candidate_cv(candidate_id, data)
        conn.execute('DELETE FROM guest_resumes WHERE token=?', (token,))
    return data


def activity_summary():
    with connect() as conn:
        logs = [dict(r) for r in conn.execute('SELECT * FROM requests ORDER BY id DESC LIMIT 100')]
        traffic = [dict(r) for r in conn.execute("SELECT date(created_at) day, COUNT(*) count FROM requests WHERE created_at >= datetime('now','-30 days') GROUP BY day")]
        uploads = [dict(r) for r in conn.execute("SELECT date(created_at) day, COUNT(*) count FROM resume_events WHERE created_at >= datetime('now','-30 days') GROUP BY day")]
        totals = dict(conn.execute('SELECT COUNT(*) requests, SUM(status>=400) errors, ROUND(AVG(duration_ms)) average_ms FROM requests').fetchone())
        guests = conn.execute('SELECT COUNT(*) FROM guest_resumes WHERE created_at>=?', (time.time()-86400,)).fetchone()[0]
    return dict(logs=logs, traffic=traffic, uploads=uploads, totals=totals, guest_resumes=guests)


def install_activity(app):
    from flask import g, request, session

    @app.before_request
    def start_request():
        g.request_started = time.monotonic()
        if any(session.get(role + '_id') for role in ('candidate', 'employer', 'admin')):
            session.permanent = True

    @app.after_request
    def record_request(response):
        if not app.testing and not request.path.startswith(('/static/', '/admin')):
            try:
                role = next((role for role in ('admin', 'candidate', 'employer') if session.get(role + '_id')), 'guest')
                # Route patterns omit user IDs; never store query strings, bodies, IPs or codes.
                with connect() as conn:
                    conn.execute('INSERT INTO requests(path,method,status,duration_ms,role) VALUES (?,?,?,?,?)',
                                 (str(request.url_rule) if request.url_rule else '<unmatched route>', request.method, response.status_code,
                                  round((time.monotonic()-g.request_started)*1000), role))
                    conn.execute("DELETE FROM requests WHERE created_at < datetime('now','-90 days')")
            except Exception:
                app.logger.exception('Request analytics unavailable')
        return response


def record_upload():
    if current_app.testing:
        return
    try:
        with connect() as conn:
            conn.execute("INSERT INTO resume_events(role) VALUES ('candidate')")
    except Exception:
        current_app.logger.exception('Resume upload analytics unavailable')
