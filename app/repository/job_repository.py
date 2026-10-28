from app.database.database import Database
import uuid


class JobRepository:

    def get_connection(self):
        return Database().get_connection()

    def fetch_by_employer_id(self, employer_id):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                j.*,
                jc.name AS category_name,
                jc.industry_id AS industry_id,
                i.name AS industry_name
            FROM jobs j
            LEFT JOIN job_categories jc ON jc.id = j.category_id
            LEFT JOIN industries i ON i.id = jc.industry_id
            WHERE j.employer_id=%s
            ORDER BY j.created_at DESC
            """,
            (employer_id,)
        )
        rows = cursor.fetchall()

        cursor.close()
        conn.close()
        return rows

    def fetch_by_id(self, job_id):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                j.*,
                jc.name AS category_name,
                jc.industry_id AS industry_id,
                i.name AS industry_name
            FROM jobs j
            LEFT JOIN job_categories jc ON jc.id = j.category_id
            LEFT JOIN industries i ON i.id = jc.industry_id
            WHERE j.id=%s
            LIMIT 1
            """,
            (job_id,),
        )
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
                id, employer_id, category_id, title, description, skills, experience_level, ai_enabled, is_technical, resume_required, deadline, responsibilities, requirements, who_should_apply, salary_insight, location
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                job_id,
                data.get("employer_id"),
                data.get("category_id"),
                data.get("title"),
                data.get("description"),
                data.get("skills"),
                data.get("experience_level"),
                1 if data.get("ai_enabled") else 0,
                1 if data.get("is_technical") else 0,
                1 if data.get("resume_required") else 0,
                data.get("deadline"),
                data.get("responsibilities"),
                data.get("requirements"),
                data.get("who_should_apply"),
                data.get("salary_insight"),
                data.get("location"),
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
            SET category_id=%s, title=%s, description=%s, skills=%s, experience_level=%s, ai_enabled=%s, is_technical=%s, resume_required=%s, deadline=%s, responsibilities=%s, requirements=%s, who_should_apply=%s, salary_insight=%s, location=%s
            WHERE id=%s AND employer_id=%s
            """,
            (
                data.get("category_id"),
                data.get("title"),
                data.get("description"),
                data.get("skills"),
                data.get("experience_level"),
                1 if data.get("ai_enabled") else 0,
                1 if data.get("is_technical") else 0,
                1 if data.get("resume_required") else 0,
                data.get("deadline"),
                data.get("responsibilities"),
                data.get("requirements"),
                data.get("who_should_apply"),
                data.get("salary_insight"),
                data.get("location"),
                job_id,
                data.get("employer_id"),
            )
        )
        conn.commit()
        updated = cursor.rowcount > 0

        cursor.close()
        conn.close()
        return updated

    def fetch_all(self, industry_id=None, category_id=None, experience_level=None, hide_expired=True):
        conn = self.get_connection()
        cursor = conn.cursor()

        query = """
            SELECT
                j.*,
                jc.name AS category_name,
                jc.industry_id AS industry_id,
                i.name AS industry_name
            FROM jobs j
            LEFT JOIN job_categories jc ON jc.id = j.category_id
            LEFT JOIN industries i ON i.id = jc.industry_id
        """
        params = []
        conditions = []
        if hide_expired:
            conditions.append("(j.deadline IS NULL OR j.deadline > NOW())")
        if industry_id:
            conditions.append("i.id=%s")
            params.append(industry_id)
        if category_id:
            conditions.append("jc.id=%s")
            params.append(category_id)
        if experience_level:
            conditions.append("j.experience_level=%s")
            params.append(experience_level)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY j.created_at DESC"

        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()

        cursor.close()
        conn.close()
        return rows
