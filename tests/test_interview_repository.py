"""Opt-in integration checks using temporary records and no external AI calls."""
import os
import uuid
import unittest
from concurrent.futures import ThreadPoolExecutor

import pymysql

from app.database.database import Database
from app.repository.interview_repository import InterviewRepository
from app.repository.job_repository import JobRepository


def connect():
    return pymysql.connect(host=os.getenv('DB_HOST'), user=os.getenv('DB_USER'),
                           password=os.getenv('DB_PASSWORD'), database=os.getenv('DB_NAME'),
                           cursorclass=pymysql.cursors.DictCursor, connect_timeout=10)


class TestInterviewRepo(InterviewRepository):
    def get_connection(self):
        return connect()


class TestJobRepo(JobRepository):
    def get_connection(self):
        return connect()


@unittest.skipUnless(os.getenv('INTERVIEW_TEST_MYSQL') == '1', 'Set INTERVIEW_TEST_MYSQL=1 for isolated database checks')
class InterviewDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.ids = [str(uuid.uuid4()) for _ in range(5)]
        self.employer, self.job, self.candidate, self.application, self.interview = self.ids
        conn = Database().get_connection()
        self.addCleanup(self.cleanup_rows)
        try:
            with conn.cursor() as cursor:
                cursor.execute('INSERT INTO employers (id, firstName, email) VALUES (%s,%s,%s)',
                               (self.employer, 'Integration test', 'test@example.invalid'))
                cursor.execute('INSERT INTO candidates (id, first_name, email) VALUES (%s,%s,%s)',
                               (self.candidate, 'Integration test', self.candidate + '@example.invalid'))
                cursor.execute('INSERT INTO jobs (id, employer_id, title) VALUES (%s,%s,%s)',
                               (self.job, self.employer, 'Temporary integration test role'))
                cursor.execute('INSERT INTO applications (id,job_id,user_id) VALUES (%s,%s,%s)',
                               (self.application, self.job, self.candidate))
                cursor.execute('INSERT INTO interviews (id,application_id,candidate_id) VALUES (%s,%s,%s)',
                               (self.interview, self.application, self.candidate))
            conn.commit()
        finally:
            conn.close()

    def cleanup_rows(self):
        conn = connect()
        try:
            with conn.cursor() as cursor:
                for table, column, ident in [
                    ('interview_responses', 'interview_id', self.interview), ('interviews', 'id', self.interview),
                    ('applications', 'id', self.application), ('jobs', 'id', self.job),
                    ('candidates', 'id', self.candidate), ('employers', 'id', self.employer)
                ]:
                    cursor.execute(f'DELETE FROM {table} WHERE {column}=%s', (ident,))
            conn.commit()
        finally:
            conn.close()

    def test_concurrent_submission_saves_one_answer_and_suggested_answer(self):
        repo = TestInterviewRepo()
        data = dict(interview_id=self.interview, question='Explain indexes', answer='Faster reads',
                    score=8, feedback='Discuss write costs', expected_answer='Indexes trade storage and writes for faster lookups.')
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: repo.insert_response_once(data, 0), range(2)))
        self.assertEqual(sorted(results), [False, True])
        rows = repo.fetch_responses_by_interview_id(self.interview)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['expected_answer'], data['expected_answer'])
        self.assertEqual(rows[0]['question_number'], 1)
        stored = repo.fetch_by_id(self.interview)
        self.assertEqual(stored['total_score'], 8)
        self.assertEqual(stored['response_count'], 1)

    def test_job_fields_round_trip_and_posted_date_is_preserved(self):
        repo = TestJobRepo()
        before = repo.fetch_by_id(self.job)
        content = dict(employer_id=self.employer, title='Temporary integration test role', description='Overview',
                       responsibilities='Build APIs', requirements='Python', who_should_apply='Backend engineers',
                       salary_insight='KES 100,000 monthly', location='Nairobi', is_technical=True)
        self.assertTrue(repo.update(self.job, content))
        after = repo.fetch_by_id(self.job)
        for key in ('description', 'responsibilities', 'requirements', 'who_should_apply', 'salary_insight', 'location'):
            self.assertEqual(after[key], content[key])
        self.assertEqual(after['created_at'], before['created_at'])
        self.assertTrue(after['is_technical'])


    def test_profile_cv_fields_persist(self):
        from app.repository.candidate_repository import CandidateRepository
        repo = CandidateRepository()
        repo.get_connection = connect
        data = dict(cv_filename="temporary-cv.docx", cv_name="CV.docx", cv_text="Python and SQL developer")
        repo.update_cv(self.candidate, data)
        stored = repo.fetch_by_id(self.candidate)
        for field, value in data.items():
            self.assertEqual(stored[field], value)
        self.assertIsNotNone(stored["cv_uploaded_at"])

    def test_pending_feedback_can_be_completed_once(self):
        repo = TestInterviewRepo()
        response_id = str(uuid.uuid4())
        data = dict(id=response_id, interview_id=self.interview, question='Explain indexes',
                    answer='Faster reads', score=None, feedback='Pending', expected_answer=None,
                    evaluation_status='pending')
        self.assertTrue(repo.insert_response_once(data, 0))
        row = repo.fetch_responses_by_interview_id(self.interview)[0]
        self.assertIsNone(row['score'])
        self.assertEqual(row['evaluation_status'], 'pending')
        evaluation = dict(score=8, feedback='Discuss write costs', expected_answer='Indexes exchange storage and write overhead for faster lookups.')
        repo.finish_evaluation(self.interview, response_id, evaluation)
        # Repeated feedback requests must not replace the score or add it twice.
        repo.finish_evaluation(self.interview, response_id, dict(evaluation, score=2))
        rows = repo.fetch_responses_by_interview_id(self.interview)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['answer'], data['answer'])
        self.assertEqual(rows[0]['score'], 8)
        self.assertEqual(rows[0]['evaluation_status'], 'completed')
        stored = repo.fetch_by_id(self.interview)
        self.assertEqual(stored['total_score'], 8)
        self.assertEqual(stored['response_count'], 1)
