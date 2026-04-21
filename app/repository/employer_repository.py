import uuid

from app.database.database import Database

class EmployerRepository:

    def get_connection(self):
        return Database().get_connection()

    def generate_uuid(self):
        return str(uuid.uuid4())

    def fetch_all(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM employers")
        result = cursor.fetchall()

        cursor.close()
        conn.close()
        return result

    def fetch_by_id(self, employer_id):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM employers WHERE id=%s", (employer_id,))
        result = cursor.fetchone()

        cursor.close()
        conn.close()
        return result

    def fetch_by_email(self, email):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM employers WHERE email=%s", (email,))
        result = cursor.fetchone()

        cursor.close()
        conn.close()
        return result

    def insert(self, data):
        conn = self.get_connection()
        cursor = conn.cursor()
        employer_id = self.generate_uuid()
        verified = 1 if data.get('verified') else 0

        cursor.execute(
            "INSERT INTO employers (id, firstName, lastName, email, phone, verified) VALUES (%s, %s, %s, %s, %s, %s)",
            (
                employer_id,
                data.get('firstName'),
                data.get('lastName'),
                data.get('email'),
                data.get('phone'),
                verified,
            )
        )

        conn.commit()

        cursor.close()
        conn.close()
        return employer_id

    def update(self, employer_id, data):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE employers SET firstName=%s, lastName=%s, email=%s, phone=%s WHERE id=%s",
            (data['firstName'], data['lastName'], data['email'], data['phone'], employer_id)
        )

        conn.commit()
        updated = cursor.rowcount > 0

        cursor.close()
        conn.close()
        return updated

    def set_verified_status(self, employer_id, verified=True):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE employers SET verified=%s WHERE id=%s",
            (1 if verified else 0, employer_id)
        )

        conn.commit()
        updated = cursor.rowcount > 0

        cursor.close()
        conn.close()
        return updated

    def delete(self, employer_id):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM employers WHERE id=%s", (employer_id,))
        conn.commit()

        deleted = cursor.rowcount > 0

        cursor.close()
        conn.close()
        return deleted
