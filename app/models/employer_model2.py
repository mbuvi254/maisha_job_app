from ..database.database import Database

class EmployerModel:
    def __init__(self):
        self.connection = Database().get_connection()
    
    
    def get_all_employers(self):
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM employers")
        return cursor.fetchall()
    
    def get_employer_by_id(self, employer_id):
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM employers WHERE id = %s", (employer_id,))
        return cursor.fetchone()
    
    def create_employer(self, employer_data):
        cursor = self.connection.cursor()
        cursor.execute("INSERT INTO employers (firstName, lastName, email, phone) VALUES (%s, %s, %s, %s)", 
                      (employer_data['firstName'], employer_data['lastName'], employer_data['email'], employer_data['phone']))
        self.connection.commit()
        return cursor.lastrowid
    
    def update_employer(self, employer_id, employer_data):
        cursor = self.connection.cursor()
        cursor.execute("UPDATE employers SET firstName = %s, lastName = %s, email = %s, phone = %s WHERE id = %s", 
                      (employer_data['firstName'], employer_data['lastName'], employer_data['email'], employer_data['phone'], employer_id))
        self.connection.commit()
        return cursor.rowcount > 0
    
    def delete_employer(self, employer_id):
        cursor = self.connection.cursor()
        cursor.execute("DELETE FROM employers WHERE id = %s", (employer_id,))
        self.connection.commit()
        return cursor.rowcount > 0
   