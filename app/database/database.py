import pymysql
from dotenv import load_dotenv
import os

load_dotenv()

class Database:
    def __init__(self):
        self.connection = None
        self.create_tables()
    
    def get_connection(self):
        if self.connection is None:
            self.connection = pymysql.connect(
                host=os.getenv("DB_HOST"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                database=os.getenv("DB_NAME"),
                cursorclass=pymysql.cursors.DictCursor
            )
        return self.connection

    def create_tables(self):
        cursor = self.get_connection().cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS employers(
                id CHAR(36) PRIMARY KEY,
                firstName TEXT,
                lastName TEXT,
                email TEXT,
                phone TEXT,
                verified TINYINT(1) NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("SHOW COLUMNS FROM employers LIKE 'id'")
        employer_id_column = cursor.fetchone()
        if employer_id_column and str(employer_id_column.get("Type", "")).lower() != "char(36)":
            cursor.execute("ALTER TABLE employers MODIFY COLUMN id CHAR(36) NOT NULL")

        cursor.execute("SHOW COLUMNS FROM employers LIKE 'verified'")
        verified_column = cursor.fetchone()
        if not verified_column:
            cursor.execute("ALTER TABLE employers ADD COLUMN verified TINYINT(1) NOT NULL DEFAULT 0")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id CHAR(36) PRIMARY KEY,
                employer_id CHAR(36) NOT NULL,
                title TEXT,
                description TEXT,
                skills TEXT,
                experience_level TEXT,
                ai_enabled BOOLEAN,
                deadline DATETIME,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("SHOW COLUMNS FROM jobs LIKE 'employer_id'")
        jobs_employer_column = cursor.fetchone()
        if not jobs_employer_column:
            cursor.execute("ALTER TABLE jobs ADD COLUMN employer_id CHAR(36) NULL AFTER id")

        cursor.execute("""
            SELECT CONSTRAINT_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'jobs'
              AND COLUMN_NAME = 'employer_id'
              AND REFERENCED_TABLE_NAME = 'employers'
        """)
        employer_fk = cursor.fetchone()
        if not employer_fk:
            try:
                cursor.execute("""
                    ALTER TABLE jobs
                    ADD CONSTRAINT fk_jobs_employer
                    FOREIGN KEY (employer_id) REFERENCES employers(id)
                    ON DELETE CASCADE
                    ON UPDATE CASCADE
                """)
            except Exception as e:
                print(f"Unable to add jobs foreign key constraint: {e}")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_verification (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_email VARCHAR(255) NOT NULL,
                otp VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS candidates (
                id CHAR(36) PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                email TEXT,
                phone TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("SHOW COLUMNS FROM candidates LIKE 'id'")
        candidate_id_column = cursor.fetchone()
        if candidate_id_column and str(candidate_id_column.get("Type", "")).lower() != "char(36)":
            cursor.execute("ALTER TABLE candidates MODIFY COLUMN id CHAR(36) NOT NULL")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id CHAR(36) PRIMARY KEY,
                job_id CHAR(36),
                user_id CHAR(36),
                status VARCHAR(50),
                score FLOAT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (job_id) REFERENCES jobs(id)
            )
        """)

        cursor.execute("SHOW COLUMNS FROM applications LIKE 'id'")
        applications_id_column = cursor.fetchone()
        if applications_id_column and str(applications_id_column.get("Type", "")).lower() != "char(36)":
            cursor.execute("ALTER TABLE applications MODIFY COLUMN id CHAR(36) NOT NULL")

        cursor.execute("SHOW COLUMNS FROM applications LIKE 'job_id'")
        applications_job_column = cursor.fetchone()
        if not applications_job_column:
            cursor.execute("ALTER TABLE applications ADD COLUMN job_id CHAR(36) NULL AFTER id")

        cursor.execute("SHOW COLUMNS FROM applications LIKE 'user_id'")
        applications_user_column = cursor.fetchone()
        if not applications_user_column:
            cursor.execute("ALTER TABLE applications ADD COLUMN user_id CHAR(36) NULL AFTER job_id")

        cursor.execute("SHOW COLUMNS FROM applications LIKE 'status'")
        applications_status_column = cursor.fetchone()
        if not applications_status_column:
            cursor.execute("ALTER TABLE applications ADD COLUMN status VARCHAR(50) NULL AFTER user_id")

        cursor.execute("SHOW COLUMNS FROM applications LIKE 'score'")
        applications_score_column = cursor.fetchone()
        if not applications_score_column:
            cursor.execute("ALTER TABLE applications ADD COLUMN score FLOAT DEFAULT 0 AFTER status")

        cursor.execute("""
            SELECT CONSTRAINT_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'applications'
              AND COLUMN_NAME = 'job_id'
              AND REFERENCED_TABLE_NAME = 'jobs'
        """)
        application_fk = cursor.fetchone()
        if not application_fk:
            try:
                cursor.execute("""
                    ALTER TABLE applications
                    ADD CONSTRAINT fk_applications_job
                    FOREIGN KEY (job_id) REFERENCES jobs(id)
                    ON DELETE CASCADE
                    ON UPDATE CASCADE
                """)
            except Exception as e:
                print(f"Unable to add applications foreign key constraint: {e}")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interviews (
                id CHAR(36) PRIMARY KEY,
                application_id CHAR(36) NOT NULL,
                candidate_id CHAR(36) NOT NULL,
                role TEXT,
                total_score FLOAT DEFAULT 0,
                response_count INT DEFAULT 0,
                status VARCHAR(50) DEFAULT 'in_progress',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (application_id) REFERENCES applications(id)
            )
        """)

        cursor.execute("SHOW COLUMNS FROM interviews LIKE 'id'")
        interviews_id_column = cursor.fetchone()
        if interviews_id_column and str(interviews_id_column.get("Type", "")).lower() != "char(36)":
            cursor.execute("ALTER TABLE interviews MODIFY COLUMN id CHAR(36) NOT NULL")

        cursor.execute("SHOW COLUMNS FROM interviews LIKE 'application_id'")
        interviews_application_column = cursor.fetchone()
        if not interviews_application_column:
            cursor.execute("ALTER TABLE interviews ADD COLUMN application_id CHAR(36) NULL AFTER id")

        cursor.execute("SHOW COLUMNS FROM interviews LIKE 'candidate_id'")
        interviews_candidate_column = cursor.fetchone()
        if not interviews_candidate_column:
            cursor.execute("ALTER TABLE interviews ADD COLUMN candidate_id CHAR(36) NULL AFTER application_id")

        cursor.execute("SHOW COLUMNS FROM interviews LIKE 'role'")
        interviews_role_column = cursor.fetchone()
        if not interviews_role_column:
            cursor.execute("ALTER TABLE interviews ADD COLUMN role TEXT NULL AFTER candidate_id")

        cursor.execute("SHOW COLUMNS FROM interviews LIKE 'total_score'")
        interviews_total_score_column = cursor.fetchone()
        if not interviews_total_score_column:
            cursor.execute("ALTER TABLE interviews ADD COLUMN total_score FLOAT DEFAULT 0 AFTER role")

        cursor.execute("SHOW COLUMNS FROM interviews LIKE 'response_count'")
        interviews_response_count_column = cursor.fetchone()
        if not interviews_response_count_column:
            cursor.execute("ALTER TABLE interviews ADD COLUMN response_count INT DEFAULT 0 AFTER total_score")

        cursor.execute("SHOW COLUMNS FROM interviews LIKE 'status'")
        interviews_status_column = cursor.fetchone()
        if not interviews_status_column:
            cursor.execute("ALTER TABLE interviews ADD COLUMN status VARCHAR(50) DEFAULT 'in_progress' AFTER response_count")

        cursor.execute("""
            SELECT CONSTRAINT_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'interviews'
              AND COLUMN_NAME = 'application_id'
              AND REFERENCED_TABLE_NAME = 'applications'
        """)
        interview_fk = cursor.fetchone()
        if not interview_fk:
            try:
                cursor.execute("""
                    ALTER TABLE interviews
                    ADD CONSTRAINT fk_interviews_application
                    FOREIGN KEY (application_id) REFERENCES applications(id)
                    ON DELETE CASCADE
                    ON UPDATE CASCADE
                """)
            except Exception as e:
                print(f"Unable to add interviews foreign key constraint: {e}")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interview_responses (
                id CHAR(36) PRIMARY KEY,
                interview_id CHAR(36) NOT NULL,
                question TEXT,
                answer TEXT,
                score FLOAT DEFAULT 0,
                feedback TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (interview_id) REFERENCES interviews(id)
            )
        """)

        cursor.execute("SHOW COLUMNS FROM interview_responses LIKE 'id'")
        response_id_column = cursor.fetchone()
        if response_id_column and str(response_id_column.get("Type", "")).lower() != "char(36)":
            cursor.execute("ALTER TABLE interview_responses MODIFY COLUMN id CHAR(36) NOT NULL")

        cursor.execute("SHOW COLUMNS FROM interview_responses LIKE 'interview_id'")
        response_interview_column = cursor.fetchone()
        if not response_interview_column:
            cursor.execute("ALTER TABLE interview_responses ADD COLUMN interview_id CHAR(36) NULL AFTER id")

        cursor.execute("SHOW COLUMNS FROM interview_responses LIKE 'question'")
        response_question_column = cursor.fetchone()
        if not response_question_column:
            cursor.execute("ALTER TABLE interview_responses ADD COLUMN question TEXT NULL AFTER interview_id")

        cursor.execute("SHOW COLUMNS FROM interview_responses LIKE 'answer'")
        response_answer_column = cursor.fetchone()
        if not response_answer_column:
            cursor.execute("ALTER TABLE interview_responses ADD COLUMN answer TEXT NULL AFTER question")

        cursor.execute("SHOW COLUMNS FROM interview_responses LIKE 'score'")
        response_score_column = cursor.fetchone()
        if not response_score_column:
            cursor.execute("ALTER TABLE interview_responses ADD COLUMN score FLOAT DEFAULT 0 AFTER answer")

        cursor.execute("SHOW COLUMNS FROM interview_responses LIKE 'feedback'")
        response_feedback_column = cursor.fetchone()
        if not response_feedback_column:
            cursor.execute("ALTER TABLE interview_responses ADD COLUMN feedback TEXT NULL AFTER score")

        cursor.execute("""
            SELECT CONSTRAINT_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'interview_responses'
              AND COLUMN_NAME = 'interview_id'
              AND REFERENCED_TABLE_NAME = 'interviews'
        """)
        response_fk = cursor.fetchone()
        if not response_fk:
            try:
                cursor.execute("""
                    ALTER TABLE interview_responses
                    ADD CONSTRAINT fk_interview_responses_interview
                    FOREIGN KEY (interview_id) REFERENCES interviews(id)
                    ON DELETE CASCADE
                    ON UPDATE CASCADE
                """)
            except Exception as e:
                print(f"Unable to add interview responses foreign key constraint: {e}")

        self.get_connection().commit()
        cursor.close()
