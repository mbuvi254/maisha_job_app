from app.database.database import Database

class VerificationRepository:

    def get_connection(self):
        return Database().get_connection()
   
       
    def save_verification_otp(self,user_email,otp):
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Keep only the latest OTP for a user so verification is deterministic.
            cursor.execute("DELETE FROM user_verification WHERE user_email=%s", (user_email,))
            cursor.execute(
                "INSERT INTO user_verification (user_email, otp) VALUES (%s, %s)",
                (user_email, otp)
            )
            conn.commit()
            print(" User verification record created successfully")
            return True
        except Exception as e:
            print("Error occurred while creating email verification record: ",e)
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        

    def get_otp(self,user_email):
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            sql = "SELECT otp FROM user_verification WHERE user_email=%s ORDER BY created_at DESC LIMIT 1"
            values=(user_email,)
            cursor.execute(sql,values)
            otp = cursor.fetchone()
            return otp['otp'] if otp else None
        except Exception as e:
            print("Error occurred while fetching OTP: ",e)
            return None
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        

    def delete_verification_otp(self, user_email):
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            sql = "DELETE FROM user_verification WHERE user_email=%s"
            values=(user_email,)
            cursor.execute(sql,values)
            conn.commit()
            print(" User verification record deleted successfully")
            return True
        except Exception as e:
            print("Error occurred while deleting email verification record: ",e)
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
