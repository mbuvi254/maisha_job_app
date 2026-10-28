import pymysql
from dotenv import load_dotenv
import os
import uuid

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
                category_id CHAR(36) NULL,
                title TEXT,
                description TEXT,
                skills TEXT,
                experience_level TEXT,
                ai_enabled BOOLEAN,
                resume_required BOOLEAN DEFAULT 0,
                deadline DATETIME,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("SHOW COLUMNS FROM jobs LIKE 'employer_id'")
        jobs_employer_column = cursor.fetchone()
        if not jobs_employer_column:
            cursor.execute("ALTER TABLE jobs ADD COLUMN employer_id CHAR(36) NULL AFTER id")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS industries (
                id CHAR(36) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_industry_name (name)
            )
        """)

        cursor.execute("SHOW COLUMNS FROM industries LIKE 'id'")
        industries_id_column = cursor.fetchone()
        if industries_id_column and str(industries_id_column.get("Type", "")).lower() != "char(36)":
            cursor.execute("ALTER TABLE industries MODIFY COLUMN id CHAR(36) NOT NULL")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_categories (
                id CHAR(36) PRIMARY KEY,
                industry_id CHAR(36) NOT NULL,
                name VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_category_name (industry_id, name)
            )
        """)

        cursor.execute("SHOW COLUMNS FROM job_categories LIKE 'id'")
        job_categories_id_column = cursor.fetchone()
        if job_categories_id_column and str(job_categories_id_column.get("Type", "")).lower() != "char(36)":
            cursor.execute("ALTER TABLE job_categories MODIFY COLUMN id CHAR(36) NOT NULL")

        cursor.execute("SHOW COLUMNS FROM job_categories LIKE 'industry_id'")
        job_categories_industry_column = cursor.fetchone()
        if not job_categories_industry_column:
            cursor.execute("ALTER TABLE job_categories ADD COLUMN industry_id CHAR(36) NULL AFTER id")

        cursor.execute("""
            SELECT CONSTRAINT_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'job_categories'
              AND COLUMN_NAME = 'industry_id'
              AND REFERENCED_TABLE_NAME = 'industries'
        """)
        category_industry_fk = cursor.fetchone()
        if not category_industry_fk:
            try:
                cursor.execute("""
                    ALTER TABLE job_categories
                    ADD CONSTRAINT fk_job_categories_industry
                    FOREIGN KEY (industry_id) REFERENCES industries(id)
                    ON DELETE CASCADE
                    ON UPDATE CASCADE
                """)
            except Exception as e:
                print(f"Unable to add job_categories industry foreign key constraint: {e}")

        cursor.execute("SHOW COLUMNS FROM jobs LIKE 'category_id'")
        jobs_category_column = cursor.fetchone()
        if not jobs_category_column:
            cursor.execute("ALTER TABLE jobs ADD COLUMN category_id CHAR(36) NULL AFTER employer_id")

        # Add structured job content without changing existing descriptions or posted dates.
        for field in ("responsibilities", "requirements", "who_should_apply", "salary_insight", "location"):
            cursor.execute("SHOW COLUMNS FROM jobs LIKE %s", (field,))
            if not cursor.fetchone():
                cursor.execute(f"ALTER TABLE jobs ADD COLUMN {field} TEXT NULL")

        cursor.execute("SHOW COLUMNS FROM jobs LIKE 'is_technical'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE jobs ADD COLUMN is_technical BOOLEAN DEFAULT 0")

        cursor.execute("SHOW COLUMNS FROM jobs LIKE 'resume_required'")
        jobs_resume_required_column = cursor.fetchone()
        if not jobs_resume_required_column:
            cursor.execute("ALTER TABLE jobs ADD COLUMN resume_required BOOLEAN DEFAULT 0 AFTER ai_enabled")

        cursor.execute("""
            SELECT CONSTRAINT_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'jobs'
              AND COLUMN_NAME = 'category_id'
              AND REFERENCED_TABLE_NAME = 'job_categories'
        """)
        job_category_fk = cursor.fetchone()
        if not job_category_fk:
            try:
                cursor.execute("""
                    ALTER TABLE jobs
                    ADD CONSTRAINT fk_jobs_category
                    FOREIGN KEY (category_id) REFERENCES job_categories(id)
                    ON DELETE SET NULL
                    ON UPDATE CASCADE
                """)
            except Exception as e:
                print(f"Unable to add jobs category foreign key constraint: {e}")

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

        cursor.execute("SELECT COUNT(*) AS total FROM industries")
        industry_count = cursor.fetchone()
        if not industry_count or int(industry_count.get("total", 0) or 0) == 0:
            default_industries = [
                "Healthcare",
                "Technology",
                "Finance",
                "Education",
            ]
            industry_ids = {}
            for name in default_industries:
                industry_id = str(uuid.uuid4())
                cursor.execute(
                    "INSERT INTO industries (id, name) VALUES (%s, %s)",
                    (industry_id, name),
                )
                industry_ids[name] = industry_id

            default_categories = {
                "Healthcare": ["Nursing", "Medical Administration", "Pharmacy"],
                "Technology": ["Software Engineering", "Data Science", "Product Management"],
                "Finance": ["Accounting", "Risk Management", "Financial Analysis"],
                "Education": ["Teaching", "Academic Administration", "Curriculum Design"],
            }
            for industry_name, category_names in default_categories.items():
                industry_id = industry_ids.get(industry_name)
                for category_name in category_names:
                    cursor.execute(
                        "INSERT INTO job_categories (id, industry_id, name) VALUES (%s, %s, %s)",
                        (str(uuid.uuid4()), industry_id, category_name),
                    )

        cursor.execute("SELECT COUNT(*) AS total FROM job_categories")
        category_count = cursor.fetchone()
        if category_count and int(category_count.get("total", 0) or 0) == 0:
            cursor.execute("SELECT id, name FROM industries")
            industries = cursor.fetchall()
            default_categories = {
                "Healthcare": ["Nursing", "Medical Administration", "Pharmacy"],
                "Technology": ["Software Engineering", "Data Science", "Product Management"],
                "Finance": ["Accounting", "Risk Management", "Financial Analysis"],
                "Education": ["Teaching", "Academic Administration", "Curriculum Design"],
            }
            for industry in industries:
                for category_name in default_categories.get(industry.get("name"), []):
                    cursor.execute(
                        "INSERT IGNORE INTO job_categories (id, industry_id, name) VALUES (%s, %s, %s)",
                        (str(uuid.uuid4()), industry.get("id"), category_name),
                    )

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auth_challenges (
                id CHAR(64) PRIMARY KEY,
                role VARCHAR(20) NOT NULL,
                email VARCHAR(254) NOT NULL,
                code_hash CHAR(64) NOT NULL,
                issued_at DOUBLE NOT NULL,
                attempts INT NOT NULL DEFAULT 0,
                consumed BOOLEAN NOT NULL DEFAULT 0,
                INDEX auth_account (role, email, issued_at)
            )
        """)

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

        for field, definition in (("cv_filename", "VARCHAR(255) NULL"), ("cv_name", "VARCHAR(255) NULL"),
                                  ("cv_text", "LONGTEXT NULL"), ("cv_uploaded_at", "DATETIME NULL")):
            cursor.execute("SHOW COLUMNS FROM candidates LIKE %s", (field,))
            if not cursor.fetchone():
                cursor.execute(f"ALTER TABLE candidates ADD COLUMN {field} {definition}")

        cursor.execute("SHOW COLUMNS FROM candidates LIKE 'id'")
        candidate_id_column = cursor.fetchone()
        if candidate_id_column and str(candidate_id_column.get("Type", "")).lower() != "char(36)":
            cursor.execute("ALTER TABLE candidates MODIFY COLUMN id CHAR(36) NOT NULL")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS saved_jobs (
                id CHAR(36) PRIMARY KEY,
                candidate_id CHAR(36) NOT NULL,
                job_id CHAR(36) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_saved_job (candidate_id, job_id)
            )
        """)

        cursor.execute("SHOW COLUMNS FROM saved_jobs LIKE 'id'")
        saved_jobs_id_column = cursor.fetchone()
        if saved_jobs_id_column and str(saved_jobs_id_column.get("Type", "")).lower() != "char(36)":
            cursor.execute("ALTER TABLE saved_jobs MODIFY COLUMN id CHAR(36) NOT NULL")

        cursor.execute("SHOW COLUMNS FROM saved_jobs LIKE 'candidate_id'")
        saved_jobs_candidate_column = cursor.fetchone()
        if not saved_jobs_candidate_column:
            cursor.execute("ALTER TABLE saved_jobs ADD COLUMN candidate_id CHAR(36) NULL AFTER id")

        cursor.execute("SHOW COLUMNS FROM saved_jobs LIKE 'job_id'")
        saved_jobs_job_column = cursor.fetchone()
        if not saved_jobs_job_column:
            cursor.execute("ALTER TABLE saved_jobs ADD COLUMN job_id CHAR(36) NULL AFTER candidate_id")

        cursor.execute("""
            SELECT CONSTRAINT_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'saved_jobs'
              AND COLUMN_NAME = 'candidate_id'
              AND REFERENCED_TABLE_NAME = 'candidates'
        """)
        saved_candidate_fk = cursor.fetchone()
        if not saved_candidate_fk:
            try:
                cursor.execute("""
                    ALTER TABLE saved_jobs
                    ADD CONSTRAINT fk_saved_jobs_candidate
                    FOREIGN KEY (candidate_id) REFERENCES candidates(id)
                    ON DELETE CASCADE
                    ON UPDATE CASCADE
                """)
            except Exception as e:
                print(f"Unable to add saved_jobs candidate foreign key constraint: {e}")

        cursor.execute("""
            SELECT CONSTRAINT_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'saved_jobs'
              AND COLUMN_NAME = 'job_id'
              AND REFERENCED_TABLE_NAME = 'jobs'
        """)
        saved_job_fk = cursor.fetchone()
        if not saved_job_fk:
            try:
                cursor.execute("""
                    ALTER TABLE saved_jobs
                    ADD CONSTRAINT fk_saved_jobs_job
                    FOREIGN KEY (job_id) REFERENCES jobs(id)
                    ON DELETE CASCADE
                    ON UPDATE CASCADE
                """)
            except Exception as e:
                print(f"Unable to add saved_jobs job foreign key constraint: {e}")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id CHAR(36) PRIMARY KEY,
                job_id CHAR(36),
                user_id CHAR(36),
                status VARCHAR(50),
                score FLOAT DEFAULT 0,
                resume_path TEXT,
                resume_name TEXT,
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

        cursor.execute("SHOW COLUMNS FROM applications LIKE 'resume_path'")
        applications_resume_path_column = cursor.fetchone()
        if not applications_resume_path_column:
            cursor.execute("ALTER TABLE applications ADD COLUMN resume_path TEXT NULL AFTER score")

        cursor.execute("SHOW COLUMNS FROM applications LIKE 'resume_name'")
        applications_resume_name_column = cursor.fetchone()
        if not applications_resume_name_column:
            cursor.execute("ALTER TABLE applications ADD COLUMN resume_name TEXT NULL AFTER resume_path")

        cursor.execute("SHOW COLUMNS FROM applications LIKE 'resume_ai_score'")
        applications_resume_ai_score_column = cursor.fetchone()
        if not applications_resume_ai_score_column:
            cursor.execute("ALTER TABLE applications ADD COLUMN resume_ai_score FLOAT DEFAULT 0 AFTER resume_name")

        cursor.execute("SHOW COLUMNS FROM applications LIKE 'resume_ai_fit'")
        applications_resume_ai_fit_column = cursor.fetchone()
        if not applications_resume_ai_fit_column:
            cursor.execute("ALTER TABLE applications ADD COLUMN resume_ai_fit TEXT NULL AFTER resume_ai_score")

        cursor.execute("SHOW COLUMNS FROM applications LIKE 'resume_ai_summary'")
        applications_resume_ai_summary_column = cursor.fetchone()
        if not applications_resume_ai_summary_column:
            cursor.execute("ALTER TABLE applications ADD COLUMN resume_ai_summary TEXT NULL AFTER resume_ai_fit")

        cursor.execute("SHOW COLUMNS FROM applications LIKE 'resume_ai_strengths'")
        applications_resume_ai_strengths_column = cursor.fetchone()
        if not applications_resume_ai_strengths_column:
            cursor.execute("ALTER TABLE applications ADD COLUMN resume_ai_strengths TEXT NULL AFTER resume_ai_summary")

        cursor.execute("SHOW COLUMNS FROM applications LIKE 'resume_ai_gaps'")
        applications_resume_ai_gaps_column = cursor.fetchone()
        if not applications_resume_ai_gaps_column:
            cursor.execute("ALTER TABLE applications ADD COLUMN resume_ai_gaps TEXT NULL AFTER resume_ai_strengths")

        cursor.execute("SHOW COLUMNS FROM applications LIKE 'resume_ai_recommendation'")
        applications_resume_ai_recommendation_column = cursor.fetchone()
        if not applications_resume_ai_recommendation_column:
            cursor.execute("ALTER TABLE applications ADD COLUMN resume_ai_recommendation TEXT NULL AFTER resume_ai_gaps")

        cursor.execute("SHOW COLUMNS FROM applications LIKE 'resume_ai_source'")
        applications_resume_ai_source_column = cursor.fetchone()
        if not applications_resume_ai_source_column:
            cursor.execute("ALTER TABLE applications ADD COLUMN resume_ai_source TEXT NULL AFTER resume_ai_recommendation")

        cursor.execute("SHOW COLUMNS FROM applications LIKE 'resume_ai_analyzed_at'")
        applications_resume_ai_analyzed_at_column = cursor.fetchone()
        if not applications_resume_ai_analyzed_at_column:
            cursor.execute("ALTER TABLE applications ADD COLUMN resume_ai_analyzed_at TIMESTAMP NULL AFTER resume_ai_source")

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

        cursor.execute("SHOW COLUMNS FROM interviews LIKE 'question_plan'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE interviews ADD COLUMN question_plan LONGTEXT NULL")

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

        cursor.execute("SHOW COLUMNS FROM interview_responses LIKE 'answer_html'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE interview_responses ADD COLUMN answer_html LONGTEXT NULL")

        cursor.execute("SHOW COLUMNS FROM interview_responses LIKE 'evaluation_status'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE interview_responses ADD COLUMN evaluation_status VARCHAR(20) DEFAULT 'completed'")
        # A missing evaluation is not a zero grade.
        cursor.execute("SHOW COLUMNS FROM interview_responses LIKE 'score'")
        if cursor.fetchone().get("Null") != "YES":
            cursor.execute("ALTER TABLE interview_responses MODIFY COLUMN score FLOAT NULL DEFAULT 0")

        cursor.execute("SHOW COLUMNS FROM interview_responses LIKE 'expected_answer'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE interview_responses ADD COLUMN expected_answer LONGTEXT NULL")
        cursor.execute("SHOW COLUMNS FROM interview_responses LIKE 'question_number'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE interview_responses ADD COLUMN question_number INT NULL")
        cursor.execute("SHOW INDEX FROM interview_responses WHERE Key_name='unique_interview_question_number'")
        if not cursor.fetchone():
            cursor.execute("CREATE UNIQUE INDEX unique_interview_question_number ON interview_responses (interview_id, question_number)")

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
