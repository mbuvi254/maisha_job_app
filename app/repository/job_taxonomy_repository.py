import uuid

from app.database.database import Database


class JobTaxonomyRepository:

    def get_connection(self):
        return Database().get_connection()

    def fetch_industries(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM industries ORDER BY name ASC"
        )
        rows = cursor.fetchall()

        cursor.close()
        conn.close()
        return rows

    def fetch_industry_by_id(self, industry_id):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM industries WHERE id=%s LIMIT 1",
            (industry_id,),
        )
        row = cursor.fetchone()

        cursor.close()
        conn.close()
        return row

    def fetch_categories(self, industry_id=None):
        conn = self.get_connection()
        cursor = conn.cursor()

        query = """
            SELECT
                jc.*,
                i.name AS industry_name
            FROM job_categories jc
            INNER JOIN industries i ON i.id = jc.industry_id
        """
        params = []
        if industry_id:
            query += " WHERE jc.industry_id=%s"
            params.append(industry_id)
        query += " ORDER BY i.name ASC, jc.name ASC"

        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()

        cursor.close()
        conn.close()
        return rows

    def fetch_category_by_id(self, category_id):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                jc.*,
                i.name AS industry_name
            FROM job_categories jc
            INNER JOIN industries i ON i.id = jc.industry_id
            WHERE jc.id=%s
            LIMIT 1
            """,
            (category_id,),
        )
        row = cursor.fetchone()

        cursor.close()
        conn.close()
        return row

    def insert_industry(self, name):
        conn = self.get_connection()
        cursor = conn.cursor()
        industry_id = str(uuid.uuid4())

        cursor.execute(
            "INSERT INTO industries (id, name) VALUES (%s, %s)",
            (industry_id, name),
        )
        conn.commit()

        cursor.close()
        conn.close()
        return industry_id

    def update_industry(self, industry_id, name):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE industries SET name=%s WHERE id=%s",
            (name, industry_id),
        )
        conn.commit()
        updated = cursor.rowcount > 0

        cursor.close()
        conn.close()
        return updated

    def delete_industry(self, industry_id):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM industries WHERE id=%s", (industry_id,))
        conn.commit()
        deleted = cursor.rowcount > 0

        cursor.close()
        conn.close()
        return deleted

    def insert_category(self, industry_id, name):
        conn = self.get_connection()
        cursor = conn.cursor()
        category_id = str(uuid.uuid4())

        cursor.execute(
            "INSERT INTO job_categories (id, industry_id, name) VALUES (%s, %s, %s)",
            (category_id, industry_id, name),
        )
        conn.commit()

        cursor.close()
        conn.close()
        return category_id

    def update_category(self, category_id, industry_id, name):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE job_categories SET industry_id=%s, name=%s WHERE id=%s",
            (industry_id, name, category_id),
        )
        conn.commit()
        updated = cursor.rowcount > 0

        cursor.close()
        conn.close()
        return updated

    def delete_category(self, category_id):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM job_categories WHERE id=%s", (category_id,))
        conn.commit()
        deleted = cursor.rowcount > 0

        cursor.close()
        conn.close()
        return deleted
